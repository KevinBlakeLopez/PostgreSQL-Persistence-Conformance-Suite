//! Catalog cases, driven with SQLx 0.9's ordinary transaction APIs.
//!
//! `explicit` and `direct` call `Transaction::commit` and `Transaction::rollback`.
//! `managed` calls `Connection::transaction`, which commits on `Ok` and calls
//! `rollback().await` on `Err`. `drop` and `direct-drop` drop an open
//! `Transaction`. That queues `ROLLBACK` and does not return a result.
//! `sql` is the isolation probe: `begin` takes no level, so the first statement
//! is `SET TRANSACTION`.

use crate::protocol::Protocol;
use crate::proxy::{Proxy, Shared};
use serde_json::{json, Map, Value};
use sqlx::postgres::{PgConnectOptions, PgPoolOptions, PgSslMode};
use sqlx::{ConnectOptions, Connection, PgConnection, PgPool, Postgres, Transaction};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::sync::oneshot;

const EXPLICIT_CONTRACT: &str = "\
sqlx 0.9.0 Transaction::commit (sqlx-core/src/transaction.rs) returns Ok after \
PgTransactionManager::commit returns. That method (sqlx-postgres/src/transaction.rs) \
executes COMMIT, or RELEASE SAVEPOINT when nested, and returns Ok when execute returns Ok. \
PgConnection::run records CommandComplete only as rows_affected \
(sqlx-postgres/src/connection/executor.rs). A command tag of ROLLBACK is not an error. \
Transaction::rollback returns Ok when ROLLBACK or ROLLBACK TO SAVEPOINT returns Ok, and \
returns that statement's error otherwise. On that error the Transaction is still open, so \
Drop calls start_rollback, which queues a second rollback and does not wait.";

const MANAGED_CONTRACT: &str = "\
Connection::transaction (sqlx-core/src/connection.rs, sqlx 0.9.0) begins a transaction, \
runs the callback, calls commit if the callback returns Ok, and calls rollback if it \
returns Err. The returned value is the callback's value when commit or rollback returns Ok. \
A rollback error is returned instead of the callback error, because rollback is awaited with ?. \
Commit and rollback are PgTransactionManager::commit and ::rollback. execute does not inspect \
a command tag of ROLLBACK. A nested Transaction::begin is SAVEPOINT _sqlx_savepoint_N.";

const DROP_CONTRACT: &str = "\
Transaction's documentation says that if neither commit nor rollback is called before the \
value goes out of scope, rollback is called on drop. Drop (sqlx-core/src/transaction.rs) \
calls PgTransactionManager::start_rollback. That method (sqlx-postgres/src/transaction.rs) \
queues a simple-query ROLLBACK or ROLLBACK TO SAVEPOINT and decrements the transaction \
depth. It does not wait, and it cannot return an error. The Drop comment says the queued \
operation runs on the next asynchronous use of the connection, including when the connection \
is returned to a pool. Floating::return_to_pool calls ping before a pooled connection can be \
checked out again, and its comment says that ping flushes transaction rollbacks.";

const SQL_CONTRACT: &str = "\
Pool::begin, Connection::begin, and Connection::transaction take no isolation argument in \
sqlx 0.9.0. This mode sends SET TRANSACTION ISOLATION LEVEL as the first statement of the \
transaction. That is application SQL, not a transaction-API option. The rest of the boundary \
is Transaction::commit or Connection::transaction, as in the explicit and managed modes.";

#[derive(Clone, Copy, PartialEq, Eq)]
enum Mode {
    Explicit,
    Managed,
    Direct,
    Drop,
    DirectDrop,
    Sql,
}

impl Mode {
    fn parse(text: &str) -> Result<Self, String> {
        Ok(match text {
            "explicit" => Self::Explicit,
            "managed" => Self::Managed,
            "direct" => Self::Direct,
            "drop" => Self::Drop,
            "direct-drop" => Self::DirectDrop,
            "sql" => Self::Sql,
            other => return Err(format!("unknown mode \"{other}\"")),
        })
    }

    fn drops(self) -> bool {
        matches!(self, Self::Drop | Self::DirectDrop)
    }

    fn managed_outer(self, case_id: &str) -> bool {
        self == Self::Managed || (self == Self::Sql && case_id == "TX-05.managed-serializable")
    }

    fn contract(self) -> &'static str {
        match self {
            Self::Managed => MANAGED_CONTRACT,
            Self::Drop | Self::DirectDrop => DROP_CONTRACT,
            Self::Sql => SQL_CONTRACT,
            Self::Explicit | Self::Direct => EXPLICIT_CONTRACT,
        }
    }
}

pub struct Case {
    pub id: String,
    pub mode: String,
    pub connection: ConnInfo,
    pub markers: HashMap<String, String>,
    pub settings: Settings,
}

pub struct ConnInfo {
    pub host: String,
    pub port: u16,
    pub user: String,
    pub password: String,
    pub database: String,
    pub application_name: String,
}

pub struct Settings {
    pub pool_max: u32,
    pub settle_ms: u64,
    pub bound_ms: u64,
    pub isolation: Option<String>,
}

pub enum Fail {
    Protocol(String),
    Setup(String),
}

pub struct Done {
    pub reported: String,
    pub basis: String,
    pub contract: String,
    pub api_error: Option<Value>,
    pub steps: Map<String, Value>,
    pub form: Option<String>,
    pub diagnostics: Value,
}

enum Db {
    Pool(PgPool),
    Conn(Option<PgConnection>),
}

enum Hold<'a> {
    Pool(sqlx::pool::PoolConnection<Postgres>),
    Direct(&'a mut PgConnection),
}

impl std::ops::Deref for Hold<'_> {
    type Target = PgConnection;
    fn deref(&self) -> &PgConnection {
        match self {
            Hold::Pool(conn) => conn,
            Hold::Direct(conn) => conn,
        }
    }
}

impl std::ops::DerefMut for Hold<'_> {
    fn deref_mut(&mut self) -> &mut PgConnection {
        match self {
            Hold::Pool(conn) => conn,
            Hold::Direct(conn) => conn,
        }
    }
}

enum CaseError {
    App(String),
    Sql(sqlx::Error),
    Protocol(String),
}

impl From<sqlx::Error> for CaseError {
    fn from(error: sqlx::Error) -> Self {
        Self::Sql(error)
    }
}

impl std::fmt::Display for CaseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::App(message) => f.write_str(message),
            Self::Sql(error) => write!(f, "{error}"),
            Self::Protocol(message) => f.write_str(message),
        }
    }
}

#[derive(Clone)]
struct CallbackEnd {
    message: String,
    error: Value,
    protocol: bool,
}

struct Ident {
    xid: String,
    pid: i32,
    isolation: Option<String>,
}

struct Run {
    case: Case,
    mode: Mode,
    proto: Arc<Protocol>,
    shared: Arc<Shared>,
    db: Db,
    server_version: String,
}

pub async fn execute(case: Case, proto: Arc<Protocol>) -> Result<Done, Fail> {
    let mode = Mode::parse(&case.mode).map_err(Fail::Setup)?;
    let shared = Shared::new(Arc::clone(&proto));
    let proxy = Proxy::start(case.connection.host.clone(), case.connection.port, Arc::clone(&shared))
        .await
        .map_err(|err| Fail::Setup(format!("the statement proxy did not start: {err}")))?;
    let opts = connect_options(&case, proxy.port());
    let db = open_db(mode, &case, &opts).await?;
    let mut run = Run { case, mode, proto, shared, db, server_version: String::new() };
    let result = run.dispatch().await;
    run.shutdown().await;
    drop(proxy);
    result
}

fn connect_options(case: &Case, port: u16) -> PgConnectOptions {
    PgConnectOptions::new()
        .host("127.0.0.1")
        .port(port)
        .username(&case.connection.user)
        .password(&case.connection.password)
        .database(&case.connection.database)
        .application_name(&case.connection.application_name)
        .ssl_mode(PgSslMode::Disable)
        .disable_statement_logging()
}

async fn open_db(mode: Mode, case: &Case, opts: &PgConnectOptions) -> Result<Db, Fail> {
    let open = match mode {
        Mode::Direct | Mode::DirectDrop => {
            PgConnection::connect_with(opts).await.map(|conn| Db::Conn(Some(conn))).map_err(|err| err.to_string())
        }
        _ => PgPoolOptions::new()
            .max_connections(case.settings.pool_max)
            .min_connections(0)
            .acquire_timeout(Duration::from_secs(20))
            .test_before_acquire(false)
            .connect_with(opts.clone())
            .await
            .map(Db::Pool)
            .map_err(|err| err.to_string()),
    };
    open.map_err(|err| Fail::Setup(redact(err, &case.connection.password)))
}

impl Run {
    async fn dispatch(&mut self) -> Result<Done, Fail> {
        self.server_version = self.read_server_version().await?;
        let id = self.case.id.as_str();
        match id {
            "CTL-01.commit" => self.control(true).await,
            "CTL-01.rollback" => self.control(false).await,
            "TX-01A.caught-error-then-commit" => self.caught_commit().await,
            "TX-01B.conn-lost-before-commit" => self.lost_before_commit().await,
            "TX-01B.commit-reply-unseen" => self.reply_unseen().await,
            "TX-02.savepoint-rollback-not-sent" => self.savepoint("not-sent").await,
            "TX-02.savepoint-rollback-rejected" => self.savepoint("rejected").await,
            "TX-02.conn-lost-before-savepoint-rollback" => self.savepoint("conn-lost").await,
            "TX-03.rollback-not-sent" => self.reuse("app").await,
            "TX-03.statement-error-rollback-not-sent" => self.reuse("statement").await,
            "TX-03.conn-lost-in-transaction" => self.reuse("conn-lost").await,
            "TX-04.nested-failure-contained" => self.nested(false).await,
            "TX-04.nested-released-outer-rollback" => self.nested(true).await,
            "TX-05.managed-serializable" | "TX-05.explicit-serializable" => self.isolation().await,
            other => Err(Fail::Setup(format!("this adapter has no implementation for {other}"))),
        }
    }

    async fn shutdown(&mut self) {
        match &mut self.db {
            Db::Pool(pool) => {
                let _ = tokio::time::timeout(Duration::from_secs(5), pool.close()).await;
            }
            Db::Conn(conn) => {
                if let Some(conn) = conn.take() {
                    let _ = tokio::time::timeout(Duration::from_secs(5), conn.close()).await;
                }
            }
        }
    }

    async fn read_server_version(&mut self) -> Result<String, Fail> {
        let password = self.case.connection.password.clone();
        let mut hold = self.checkout().await?;
        let row: (String,) = sqlx::query_as("select current_setting('server_version')")
            .fetch_one(&mut *hold)
            .await
            .map_err(|err| Fail::Setup(redact(err.to_string(), &password)))?;
        Ok(row.0)
    }

    async fn checkout(&mut self) -> Result<Hold<'_>, Fail> {
        match &mut self.db {
            Db::Pool(pool) => {
                let conn = pool.acquire().await.map_err(|err| Fail::Setup(redact(err.to_string(), &self.case.connection.password)))?;
                Ok(Hold::Pool(conn))
            }
            Db::Conn(conn) => Ok(Hold::Direct(conn.as_mut().ok_or_else(|| Fail::Setup("the direct connection is already closed".into()))?)),
        }
    }

    fn marker(&self, label: &str) -> Result<String, Fail> {
        self.case.markers.get(label).cloned().ok_or_else(|| Fail::Setup(format!("the case did not provide marker \"{label}\"")))
    }

    fn finish(&self, mut done: Done) -> Done {
        done.steps.insert("driver".into(), self.shared.trace());
        done.diagnostics = json!({
            "server_version": self.server_version,
            "rustc": env!("PPCS_RUSTC"),
            "cargo": env!("PPCS_CARGO"),
            "sqlx": env!("PPCS_SQLX_VERSION"),
            "sqlx_postgres": env!("PPCS_SQLX_POSTGRES_VERSION"),
            "sqlx_core": env!("PPCS_SQLX_CORE_VERSION"),
            "tokio": env!("PPCS_TOKIO_VERSION"),
            "features": ["runtime-tokio", "postgres"],
            "compile_time_macros": false,
            "driver": self.shared.trace(),
        });
        done
    }

    async fn control(&mut self, commit: bool) -> Result<Done, Fail> {
        let marker = self.marker("tx")?;
        if self.mode.managed_outer(&self.case.id) && !commit {
            return self.managed_rollback(&marker).await;
        }
        if self.mode.managed_outer(&self.case.id) && commit {
            return self.managed_commit(&marker).await;
        }
        let drops = self.mode.drops();
        let proto = Arc::clone(&self.proto);
        let mut hold = self.checkout().await?;
        let mut tx = Connection::begin(&mut *hold).await.map_err(setup_sql)?;
        insert_marker(&mut tx, &marker).await.map_err(setup_sql)?;
        let ident = identify(&mut tx, false).await.map_err(setup_sql)?;
        cp_proto(&proto, "before-end", Some(&ident)).map_err(Fail::Protocol)?;
        let outcome = if commit {
            let outcome = map_commit(tx.commit().await);
            drop(hold);
            outcome
        } else if drops {
            drop(tx);
            drop(hold);
            rolled_back_drop("application error: the transaction fails")
        } else {
            let outcome = map_explicit_rollback(tx.rollback().await, "application error: the transaction fails");
            drop(hold);
            outcome
        };
        cp_proto(&proto, "after-end", None).map_err(Fail::Protocol)?;
        Ok(self.finish(self.outcome(outcome, Map::new(), None)))
    }

    async fn managed_commit(&mut self, marker: &str) -> Result<Done, Fail> {
        let marker = marker.to_string();
        let proto = Arc::clone(&self.proto);
        let mut hold = self.checkout().await?;
        let end = Arc::new(Mutex::new(None));
        let result = Connection::transaction(&mut *hold, {
            let end = Arc::clone(&end);
            move |tx| {
                let marker = marker.clone();
                let proto = Arc::clone(&proto);
                let end = Arc::clone(&end);
                Box::pin(async move {
                    insert_marker(&mut **tx, &marker).await?;
                    let ident = identify(&mut **tx, false).await?;
                    cp_proto(&proto, "before-end", Some(&ident)).map_err(CaseError::Protocol)?;
                    let _ = end;
                    Ok::<(), CaseError>(())
                })
            }
        })
        .await;
        drop(hold);
        self.cp("after-end", None)?;
        Ok(self.finish(self.outcome(map_managed(result, &end), Map::new(), None)))
    }

    async fn managed_rollback(&mut self, marker: &str) -> Result<Done, Fail> {
        let marker = marker.to_string();
        let proto = Arc::clone(&self.proto);
        let mut hold = self.checkout().await?;
        let end = Arc::new(Mutex::new(None));
        let result = Connection::transaction(&mut *hold, {
            let end = Arc::clone(&end);
            move |tx| {
                let marker = marker.clone();
                let proto = Arc::clone(&proto);
                let end = Arc::clone(&end);
                Box::pin(async move {
                    insert_marker(&mut **tx, &marker).await?;
                    let ident = identify(&mut **tx, false).await?;
                    cp_proto(&proto, "before-end", Some(&ident)).map_err(CaseError::Protocol)?;
                    let error = CaseError::App("application error: the transaction fails".to_string());
                    *end.lock().expect("callback") = Some(callback_end(&error));
                    Err(error)
                })
            }
        })
        .await;
        drop(hold);
        self.cp("after-end", None)?;
        Ok(self.finish(self.outcome(map_managed(result, &end), Map::new(), None)))
    }

    async fn caught_commit(&mut self) -> Result<Done, Fail> {
        let marker = self.marker("tx")?;
        if self.mode.managed_outer(&self.case.id) {
            return self.caught_managed(&marker).await;
        }
        let proto = Arc::clone(&self.proto);
        let mut hold = self.checkout().await?;
        let mut tx = Connection::begin(&mut *hold).await.map_err(setup_sql)?;
        insert_marker(&mut tx, &marker).await.map_err(setup_sql)?;
        let ident = identify(&mut tx, false).await.map_err(setup_sql)?;
        cp_proto(&proto, "after-write", Some(&ident)).map_err(Fail::Protocol)?;
        let mut steps = Map::new();
        match insert_taken(&mut tx).await {
            Err(err) => steps.insert("violation".into(), sql_error(&err)),
            Ok(()) => steps.insert("violation".into(), json!({"class": "sqlx::Error", "message": "the duplicate insert succeeded"})),
        };
        proto.checkpoint("before-end", None, Some(ident.pid), None).map_err(Fail::Protocol)?;
        let outcome = map_commit(tx.commit().await);
        drop(hold);
        cp_proto(&proto, "after-end", None).map_err(Fail::Protocol)?;
        Ok(self.finish(self.outcome(outcome, steps, None)))
    }

    async fn caught_managed(&mut self, marker: &str) -> Result<Done, Fail> {
        let marker = marker.to_string();
        let proto = Arc::clone(&self.proto);
        let violation: Arc<Mutex<Option<Value>>> = Arc::new(Mutex::new(None));
        let mut hold = self.checkout().await?;
        let result = Connection::transaction(&mut *hold, {
            let violation = Arc::clone(&violation);
            move |tx| {
                let marker = marker.clone();
                let proto = Arc::clone(&proto);
                let violation = Arc::clone(&violation);
                Box::pin(async move {
                    insert_marker(&mut **tx, &marker).await?;
                    let ident = identify(&mut **tx, false).await?;
                    cp_proto(&proto, "after-write", Some(&ident)).map_err(CaseError::Protocol)?;
                    match insert_taken(&mut **tx).await {
                        Err(err) => *violation.lock().expect("violation") = Some(sql_error(&err)),
                        Ok(()) => {
                            *violation.lock().expect("violation") = Some(json!({"class": "sqlx::Error", "message": "the duplicate insert succeeded"}));
                        }
                    }
                    // The transaction is aborted, so this checkpoint cannot query.
                    // The pid is the one captured at after-write.
                    proto.checkpoint("before-end", None, Some(ident.pid), None).map_err(CaseError::Protocol)?;
                    Ok(())
                })
            }
        })
        .await;
        // The closure above checkpoints before-end twice if both calls run. The explicit
        // checkpoint is the one that carries the pid. Remove the None call by not using it.
        drop(hold);
        self.cp("after-end", None)?;
        let mut steps = Map::new();
        if let Some(found) = violation.lock().expect("violation").clone() {
            steps.insert("violation".into(), found);
        }
        let end: Mutex<Option<CallbackEnd>> = Mutex::new(None);
        Ok(self.finish(self.outcome(map_managed(result, &end), steps, None)))
    }

    async fn lost_before_commit(&mut self) -> Result<Done, Fail> {
        self.commit_after_checkpoint(true).await
    }

    async fn reply_unseen(&mut self) -> Result<Done, Fail> {
        self.commit_after_checkpoint(false).await
    }

    async fn commit_after_checkpoint(&mut self, settle: bool) -> Result<Done, Fail> {
        let marker = self.marker("tx")?;
        if self.mode.managed_outer(&self.case.id) {
            return self.managed_commit_after(&marker, settle).await;
        }
        let proto = Arc::clone(&self.proto);
        let settle_ms = self.case.settings.settle_ms;
        let mut hold = self.checkout().await?;
        let mut tx = Connection::begin(&mut *hold).await.map_err(setup_sql)?;
        insert_marker(&mut tx, &marker).await.map_err(setup_sql)?;
        let ident = identify(&mut tx, false).await.map_err(setup_sql)?;
        cp_proto(&proto, "before-end", Some(&ident)).map_err(Fail::Protocol)?;
        if settle {
            tokio::time::sleep(Duration::from_millis(settle_ms)).await;
        }
        let outcome = map_commit(tx.commit().await);
        drop(hold);
        cp_proto(&proto, "after-end", None).map_err(Fail::Protocol)?;
        Ok(self.finish(self.outcome(outcome, Map::new(), None)))
    }

    async fn managed_commit_after(&mut self, marker: &str, settle: bool) -> Result<Done, Fail> {
        let marker = marker.to_string();
        let proto = Arc::clone(&self.proto);
        let settle_ms = self.case.settings.settle_ms;
        let mut hold = self.checkout().await?;
        let end = Arc::new(Mutex::new(None));
        let result = Connection::transaction(&mut *hold, {
            let end = Arc::clone(&end);
            move |tx| {
                let marker = marker.clone();
                let proto = Arc::clone(&proto);
                let end = Arc::clone(&end);
                Box::pin(async move {
                    insert_marker(&mut **tx, &marker).await?;
                    let ident = identify(&mut **tx, false).await?;
                    cp_proto(&proto, "before-end", Some(&ident)).map_err(CaseError::Protocol)?;
                    if settle {
                        tokio::time::sleep(Duration::from_millis(settle_ms)).await;
                    }
                    let _ = end;
                    Ok(())
                })
            }
        })
        .await;
        drop(hold);
        self.cp("after-end", None)?;
        Ok(self.finish(self.outcome(map_managed(result, &end), Map::new(), None)))
    }

    async fn savepoint(&mut self, kind: &'static str) -> Result<Done, Fail> {
        if self.mode.managed_outer(&self.case.id) {
            return self.savepoint_managed(kind).await;
        }
        let outer = self.marker("outer")?;
        let inner = self.marker("inner")?;
        let proto = Arc::clone(&self.proto);
        let shared = Arc::clone(&self.shared);
        let drops = self.mode.drops();
        let settle_ms = self.case.settings.settle_ms;
        let form = savepoint_form(self.mode);
        let mut hold = self.checkout().await?;
        let mut tx = Connection::begin(&mut *hold).await.map_err(setup_sql)?;
        insert_marker(&mut tx, &outer).await.map_err(setup_sql)?;
        let ident = identify(&mut tx, false).await.map_err(setup_sql)?;
        cp_proto(&proto, "outer-after-write", Some(&ident)).map_err(Fail::Protocol)?;
        let mut nested = Map::new();
        nested.insert("caught".into(), json!(false));
        nested.insert("completed".into(), json!(false));
        let mut rx = None;
        inner_scope(&proto, &shared, drops, settle_ms, &mut tx, &inner, kind, &mut nested, &mut rx).await?;
        // The outer scope ends normally. A dropped inner Transaction has only queued
        // ROLLBACK TO; commit's first wait flushes that queue, which is where a drop-mode
        // fault fires. Waiting for the fault before commit would deadlock.
        let outcome = map_commit(tx.commit().await);
        drop(rx);
        let pid = ident.pid;
        drop(hold);
        proto.checkpoint("after-outer", None, Some(pid), None).map_err(Fail::Protocol)?;
        cp_proto(&proto, "after-end", None).map_err(Fail::Protocol)?;
        let mut steps = Map::new();
        steps.insert("nested".into(), Value::Object(nested));
        if kind != "conn-lost" {
            steps.insert("fault".into(), shared.report());
        }
        Ok(self.finish(self.outcome(outcome, steps, Some(form))))
    }

    async fn savepoint_managed(&mut self, kind: &'static str) -> Result<Done, Fail> {
        let outer = self.marker("outer")?;
        let inner_marker = self.marker("inner")?;
        let proto = Arc::clone(&self.proto);
        let shared = Arc::clone(&self.shared);
        let settle_ms = self.case.settings.settle_ms;
        let nested_state = Arc::new(Mutex::new(Map::new()));
        let pid_slot = Arc::new(Mutex::new(0_i32));
        let end: Arc<Mutex<Option<CallbackEnd>>> = Arc::new(Mutex::new(None));
        let mut hold = self.checkout().await?;
        let result = Connection::transaction(&mut *hold, {
            let nested_state = Arc::clone(&nested_state);
            let pid_slot = Arc::clone(&pid_slot);
            let end = Arc::clone(&end);
            move |tx| {
                let outer = outer.clone();
                let inner_marker = inner_marker.clone();
                let proto = Arc::clone(&proto);
                let shared = Arc::clone(&shared);
                let nested_state = Arc::clone(&nested_state);
                let pid_slot = Arc::clone(&pid_slot);
                let end = Arc::clone(&end);
                Box::pin(async move {
                    insert_marker(&mut **tx, &outer).await?;
                    let ident = identify(&mut **tx, false).await?;
                    *pid_slot.lock().expect("pid") = ident.pid;
                    cp_proto(&proto, "outer-after-write", Some(&ident)).map_err(CaseError::Protocol)?;
                    let mut inner = Connection::begin(&mut **tx).await?;
                    insert_marker(&mut inner, &inner_marker).await?;
                    let inner_ident = identify(&mut inner, false).await?;
                    cp_proto(&proto, "inner-after-write", Some(&inner_ident)).map_err(CaseError::Protocol)?;
                    if kind == "conn-lost" {
                        tokio::time::sleep(Duration::from_millis(settle_ms)).await;
                    } else {
                        shared.set_pid(inner_ident.pid);
                        let rx = match kind {
                            "rejected" => shared.arm_savepoint_rewrite(),
                            _ => shared.arm_savepoint_reject(),
                        };
                        let rolled = inner.rollback().await;
                        drop(rx);
                        let mut nested = Map::new();
                        nested.insert("caught".into(), json!(true));
                        nested.insert("completed".into(), json!(false));
                        nested.insert("error".into(), match &rolled {
                            Ok(()) => app_error("application error: the nested scope fails"),
                            Err(err) => sql_error(err),
                        });
                        *nested_state.lock().expect("nested") = nested;
                        let _ = end;
                        return Ok(());
                    }
                    let rolled = inner.rollback().await;
                    let mut nested = Map::new();
                    nested.insert("caught".into(), json!(true));
                    nested.insert("completed".into(), json!(false));
                    nested.insert("error".into(), match &rolled {
                        Ok(()) => app_error("application error: the nested scope fails"),
                        Err(err) => sql_error(err),
                    });
                    *nested_state.lock().expect("nested") = nested;
                    Ok(())
                })
            }
        })
        .await;
        drop(hold);
        let pid = *pid_slot.lock().expect("pid");
        self.proto.checkpoint("after-outer", None, Some(pid), None).map_err(Fail::Protocol)?;
        self.cp("after-end", None)?;
        let mut steps = Map::new();
        steps.insert("nested".into(), Value::Object(nested_state.lock().expect("nested").clone()));
        if kind != "conn-lost" {
            steps.insert("fault".into(), self.shared.report());
        }
        Ok(self.finish(self.outcome(map_managed(result, &end), steps, Some(savepoint_form(Mode::Managed)))))
    }

    async fn reuse(&mut self, kind: &'static str) -> Result<Done, Fail> {
        let doomed = self.marker("doomed")?;
        let next = self.marker("next")?;
        let mut unit1_pid = 0;
        let mut steps = Map::new();
        let mut rx = None;
        let outcome = if self.mode.managed_outer(&self.case.id) {
            self.reuse_managed(kind, &doomed, &mut unit1_pid, &mut steps).await?
        } else {
            self.reuse_explicit(kind, &doomed, &mut unit1_pid, &mut steps, &mut rx).await?
        };
        if let Some(rx) = rx {
            let _ = tokio::time::timeout(Duration::from_secs(5), rx).await;
        }
        self.cp_pid("after-unit1", unit1_pid)?;
        let started = Instant::now();
        let bound = Duration::from_millis(self.case.settings.bound_ms);
        let unit2 = self.unit2(&next);
        let mut unit2_pid = None;
        let unit2_step = match tokio::time::timeout(bound, unit2).await {
            Ok(Ok((pid, outcome))) => {
                unit2_pid = pid;
                let mut body = outcome_json(&outcome);
                body.insert("outcome".into(), json!("completed"));
                body.insert("elapsed_ms".into(), json!(started.elapsed().as_millis() as u64));
                Value::Object(body)
            }
            Ok(Err(Fail::Protocol(message))) => return Err(Fail::Protocol(message)),
            Ok(Err(Fail::Setup(message))) => {
                json!({"outcome": "completed", "elapsed_ms": started.elapsed().as_millis() as u64, "reported": "failed", "api_error": {"class": "setup", "message": message}})
            }
            Err(_) => json!({"outcome": "pending", "elapsed_ms": self.case.settings.bound_ms}),
        };
        steps.insert("unit2".into(), unit2_step);
        steps.insert("reuse".into(), json!({
            "unit1_pid": unit1_pid,
            "unit2_pid": unit2_pid,
            "same_backend": unit2_pid == Some(unit1_pid) && unit1_pid != 0,
        }));
        if kind != "conn-lost" {
            steps.insert("fault".into(), self.shared.report());
        }
        self.cp("after-end", None)?;
        Ok(self.finish(self.outcome(outcome, steps, None)))
    }

    async fn reuse_explicit(
        &mut self,
        kind: &'static str,
        doomed: &str,
        unit1_pid: &mut i32,
        steps: &mut Map<String, Value>,
        rx_slot: &mut Option<oneshot::Receiver<()>>,
    ) -> Result<Outcome, Fail> {
        let proto = Arc::clone(&self.proto);
        let shared = Arc::clone(&self.shared);
        let drops = self.mode.drops();
        let settle_ms = self.case.settings.settle_ms;
        let mut hold = self.checkout().await?;
        let mut tx = Connection::begin(&mut *hold).await.map_err(setup_sql)?;
        insert_marker(&mut tx, doomed).await.map_err(setup_sql)?;
        let ident = identify(&mut tx, false).await.map_err(setup_sql)?;
        *unit1_pid = ident.pid;
        cp_proto(&proto, "unit1-after-write", Some(&ident)).map_err(Fail::Protocol)?;
        if kind == "conn-lost" {
            tokio::time::sleep(Duration::from_millis(settle_ms)).await;
        } else {
            shared.set_pid(ident.pid);
            *rx_slot = Some(shared.arm_root_reject());
        }
        if kind == "statement" {
            match insert_taken(&mut tx).await {
                Err(err) => steps.insert("violation".into(), sql_error(&err)),
                Ok(()) => steps.insert("violation".into(), json!({"class": "sqlx::Error", "message": "the duplicate insert succeeded"})),
            };
        }
        let outcome = if drops {
            drop(tx);
            drop(hold);
            if kind == "statement" {
                rolled_back_drop("unique violation inside the transaction; Transaction dropped")
            } else {
                rolled_back_drop("application error: unit 1 fails")
            }
        } else {
            let app = if kind == "statement" { "unique_violation" } else { "application error: unit 1 fails" };
            let outcome = map_explicit_rollback(tx.rollback().await, app);
            drop(hold);
            outcome
        };
        Ok(outcome)
    }

    async fn reuse_managed(
        &mut self,
        kind: &'static str,
        doomed: &str,
        unit1_pid: &mut i32,
        steps: &mut Map<String, Value>,
    ) -> Result<Outcome, Fail> {
        let doomed = doomed.to_string();
        let proto = Arc::clone(&self.proto);
        let shared = Arc::clone(&self.shared);
        let settle_ms = self.case.settings.settle_ms;
        let pid_slot = Arc::new(Mutex::new(0_i32));
        let violation = Arc::new(Mutex::new(None));
        let end = Arc::new(Mutex::new(None));
        let mut hold = self.checkout().await?;
        let result = Connection::transaction(&mut *hold, {
            let pid_slot = Arc::clone(&pid_slot);
            let violation = Arc::clone(&violation);
            let end = Arc::clone(&end);
            move |tx| {
                let doomed = doomed.clone();
                let proto = Arc::clone(&proto);
                let shared = Arc::clone(&shared);
                let pid_slot = Arc::clone(&pid_slot);
                let violation = Arc::clone(&violation);
                let end = Arc::clone(&end);
                Box::pin(async move {
                    insert_marker(&mut **tx, &doomed).await?;
                    let ident = identify(&mut **tx, false).await?;
                    *pid_slot.lock().expect("pid") = ident.pid;
                    cp_proto(&proto, "unit1-after-write", Some(&ident)).map_err(CaseError::Protocol)?;
                    if kind == "conn-lost" {
                        tokio::time::sleep(Duration::from_millis(settle_ms)).await;
                    } else {
                        shared.set_pid(ident.pid);
                        let _rx = shared.arm_root_reject();
                        // Keep the receiver alive until rollback returns, so the proxy can send.
                        // It is dropped at the end of this callback, after transaction() has
                        // called rollback. That is too early if rollback awaits the fault.
                        // Hold it across the error return: transaction() rolls back before this
                        // future is dropped. The receiver must outlive rollback. Store it where
                        // the outer future keeps it... it cannot. The send is lossy if the
                        // receiver is dropped, and the checkpoint still runs. Dropping _rx at the
                        // end of the callback is before transaction()'s rollback. So arm here and
                        // leak the receiver until rollback by moving it into the error path's
                        // CaseError? Simpler: forget the receiver so it stays alive.
                        std::mem::forget(_rx);
                    }
                    if kind == "statement" {
                        match insert_taken(&mut **tx).await {
                            Err(err) => {
                                let info = sql_error(&err);
                                *violation.lock().expect("violation") = Some(info.clone());
                                let error = CaseError::Sql(err);
                                *end.lock().expect("callback") = Some(callback_end(&error));
                                return Err(error);
                            }
                            Ok(()) => {
                                *violation.lock().expect("violation") = Some(json!({"class": "sqlx::Error", "message": "the duplicate insert succeeded"}));
                            }
                        }
                    }
                    let error = CaseError::App("application error: unit 1 fails".to_string());
                    *end.lock().expect("callback") = Some(callback_end(&error));
                    Err(error)
                })
            }
        })
        .await;
        drop(hold);
        *unit1_pid = *pid_slot.lock().expect("pid");
        if let Some(found) = violation.lock().expect("violation").clone() {
            steps.insert("violation".into(), found);
        }
        Ok(map_managed(result, &end))
    }

    async fn unit2(&mut self, marker: &str) -> Result<(Option<i32>, Outcome), Fail> {
        let proto = Arc::clone(&self.proto);
        let mut hold = self.checkout().await?;
        let mut tx = Connection::begin(&mut *hold).await.map_err(setup_sql)?;
        insert_marker(&mut tx, marker).await.map_err(setup_sql)?;
        let ident = identify(&mut tx, false).await.map_err(setup_sql)?;
        cp_proto(&proto, "unit2-after-write", Some(&ident)).map_err(Fail::Protocol)?;
        let outcome = map_commit(tx.commit().await);
        Ok((Some(ident.pid), outcome))
    }

    async fn nested(&mut self, release: bool) -> Result<Done, Fail> {
        let outer = self.marker("outer")?;
        let inner_marker = self.marker("inner")?;
        let form = Some(nested_form(self.mode));
        if self.mode.managed_outer(&self.case.id) {
            return self.nested_managed(release, &outer, &inner_marker, form).await;
        }
        let proto = Arc::clone(&self.proto);
        let drops = self.mode.drops();
        let mut hold = self.checkout().await?;
        let mut tx = Connection::begin(&mut *hold).await.map_err(setup_sql)?;
        insert_marker(&mut tx, &outer).await.map_err(setup_sql)?;
        let mut nested = Map::new();
        let mut inner = Connection::begin(&mut *tx).await.map_err(setup_sql)?;
        insert_marker(&mut inner, &inner_marker).await.map_err(setup_sql)?;
        let ident = identify(&mut inner, false).await.map_err(setup_sql)?;
        cp_proto(&proto, "inner-after-write", Some(&ident)).map_err(Fail::Protocol)?;
        if release {
            inner.commit().await.map_err(setup_sql)?;
            nested.insert("completed".into(), json!(true));
            nested.insert("caught".into(), json!(false));
        } else if drops {
            drop(inner);
            nested.insert("caught".into(), json!(true));
            nested.insert("error".into(), app_error("application error: the nested scope fails"));
            nested.insert("completed".into(), json!(false));
        } else {
            inner.rollback().await.map_err(setup_sql)?;
            nested.insert("caught".into(), json!(true));
            nested.insert("error".into(), app_error("application error: the nested scope fails"));
            nested.insert("completed".into(), json!(false));
        }
        let outcome = if release {
            if drops {
                drop(tx);
                rolled_back_drop("application error: the outer transaction fails")
            } else {
                map_explicit_rollback(tx.rollback().await, "application error: the outer transaction fails")
            }
        } else {
            map_commit(tx.commit().await)
        };
        drop(hold);
        cp_proto(&proto, "after-end", None).map_err(Fail::Protocol)?;
        let mut steps = Map::new();
        steps.insert("nested".into(), Value::Object(nested));
        Ok(self.finish(self.outcome(outcome, steps, form)))
    }

    async fn nested_managed(&mut self, release: bool, outer: &str, inner_marker: &str, form: Option<String>) -> Result<Done, Fail> {
        let outer = outer.to_string();
        let inner_marker = inner_marker.to_string();
        let proto = Arc::clone(&self.proto);
        let nested_state = Arc::new(Mutex::new(Map::new()));
        let end = Arc::new(Mutex::new(None));
        let mut hold = self.checkout().await?;
        let result = Connection::transaction(&mut *hold, {
            let nested_state = Arc::clone(&nested_state);
            let end = Arc::clone(&end);
            move |tx| {
                let outer = outer.clone();
                let inner_marker = inner_marker.clone();
                let proto = Arc::clone(&proto);
                let nested_state = Arc::clone(&nested_state);
                let end = Arc::clone(&end);
                Box::pin(async move {
                    insert_marker(&mut **tx, &outer).await?;
                    let mut inner = Connection::begin(&mut **tx).await?;
                    insert_marker(&mut inner, &inner_marker).await?;
                    let ident = identify(&mut inner, false).await?;
                    cp_proto(&proto, "inner-after-write", Some(&ident)).map_err(CaseError::Protocol)?;
                    let mut nested = Map::new();
                    if release {
                        inner.commit().await?;
                        nested.insert("completed".into(), json!(true));
                        nested.insert("caught".into(), json!(false));
                        *nested_state.lock().expect("nested") = nested;
                        let error = CaseError::App("application error: the outer transaction fails".to_string());
                        *end.lock().expect("callback") = Some(callback_end(&error));
                        Err(error)
                    } else {
                        inner.rollback().await?;
                        nested.insert("caught".into(), json!(true));
                        nested.insert("error".into(), app_error("application error: the nested scope fails"));
                        nested.insert("completed".into(), json!(false));
                        *nested_state.lock().expect("nested") = nested;
                        Ok(())
                    }
                })
            }
        })
        .await;
        drop(hold);
        self.cp("after-end", None)?;
        let mut steps = Map::new();
        steps.insert("nested".into(), Value::Object(nested_state.lock().expect("nested").clone()));
        Ok(self.finish(self.outcome(map_managed(result, &end), steps, form)))
    }

    async fn isolation(&mut self) -> Result<Done, Fail> {
        let marker = self.marker("tx")?;
        let level = self.case.settings.isolation.clone().unwrap_or_else(|| "serializable".to_string());
        let explicit = self.case.id == "TX-05.explicit-serializable";
        let mut steps = Map::new();
        steps.insert("isolation_api".into(), json!("SET TRANSACTION"));
        steps.insert("requested".into(), json!(level));
        let started = self.isolation_body(&marker, &level, explicit).await;
        match started {
            Ok(outcome) => {
                self.cp("after-end", None)?;
                Ok(self.finish(self.outcome(outcome, steps, Some(isolation_form(explicit)))))
            }
            Err(start) => {
                let proto = Arc::clone(&self.proto);
                let mut hold = self.checkout().await?;
                match plain_baseline(&mut hold, &proto).await {
                    Ok(()) => {}
                    Err(err) => {
                        steps.insert("baseline".into(), json!({"error": sql_error_value(&err)}));
                    }
                }
                drop(hold);
                cp_proto(&proto, "after-end", None).map_err(Fail::Protocol)?;
                let outcome = Outcome {
                    reported: "failed".into(),
                    basis: "the isolation statement or begin returned an error before the transaction body".into(),
                    api_error: Some(start),
                };
                Ok(self.finish(self.outcome(outcome, steps, Some(isolation_form(explicit)))))
            }
        }
    }

    async fn isolation_body(&mut self, marker: &str, level: &str, explicit: bool) -> Result<Outcome, Value> {
        if !explicit && self.mode == Mode::Sql {
            return self.isolation_managed(marker, level).await;
        }
        let proto = Arc::clone(&self.proto);
        let mut hold = self.checkout().await.map_err(|err| json!({"class": "setup", "message": fail_text(err)}))?;
        let mut tx = Connection::begin(&mut *hold).await.map_err(|err| sql_error(&err))?;
        set_isolation(&mut tx, level).await.map_err(|err| sql_error(&err))?;
        insert_marker(&mut tx, marker).await.map_err(|err| sql_error(&err))?;
        read_marker(&mut tx, marker).await.map_err(|err| sql_error(&err))?;
        let ident = identify(&mut tx, true).await.map_err(|err| sql_error(&err))?;
        cp_proto(&proto, "after-read", Some(&ident)).map_err(|err| json!({"class": "protocol", "message": err}))?;
        let outcome = map_commit(tx.commit().await);
        Ok(outcome)
    }

    async fn isolation_managed(&mut self, marker: &str, level: &str) -> Result<Outcome, Value> {
        let marker = marker.to_string();
        let level = level.to_string();
        let proto = Arc::clone(&self.proto);
        let mut hold = self.checkout().await.map_err(|err| json!({"class": "setup", "message": fail_text(err)}))?;
        let end = Arc::new(Mutex::new(None));
        let result = Connection::transaction(&mut *hold, {
            let end = Arc::clone(&end);
            move |tx| {
                let marker = marker.clone();
                let level = level.clone();
                let proto = Arc::clone(&proto);
                let end = Arc::clone(&end);
                Box::pin(async move {
                    set_isolation(&mut **tx, &level).await?;
                    insert_marker(&mut **tx, &marker).await?;
                    read_marker(&mut **tx, &marker).await?;
                    let ident = identify(&mut **tx, true).await?;
                    cp_proto(&proto, "after-read", Some(&ident)).map_err(CaseError::Protocol)?;
                    let _ = end;
                    Ok::<(), CaseError>(())
                })
            }
        })
        .await;
        Ok(map_managed(result, &end))
    }

    fn cp(&self, name: &str, ident: Option<&Ident>) -> Result<(), Fail> {
        cp_proto(&self.proto, name, ident).map_err(Fail::Protocol)
    }

    fn cp_pid(&self, name: &str, pid: i32) -> Result<(), Fail> {
        self.proto.checkpoint(name, None, Some(pid), None).map_err(Fail::Protocol)
    }

    fn outcome(&self, outcome: Outcome, steps: Map<String, Value>, form: Option<String>) -> Done {
        Done {
            reported: outcome.reported,
            basis: outcome.basis,
            contract: self.mode.contract().to_string(),
            api_error: outcome.api_error,
            steps,
            form,
            diagnostics: Value::Null,
        }
    }
}

struct Outcome {
    reported: String,
    basis: String,
    api_error: Option<Value>,
}

async fn inner_scope(
    proto: &Protocol,
    shared: &Shared,
    drops: bool,
    settle_ms: u64,
    tx: &mut Transaction<'_, Postgres>,
    marker: &str,
    kind: &'static str,
    nested: &mut Map<String, Value>,
    rx_slot: &mut Option<oneshot::Receiver<()>>,
) -> Result<(), Fail> {
    let mut inner = Connection::begin(&mut **tx).await.map_err(setup_sql)?;
    insert_marker(&mut inner, marker).await.map_err(setup_sql)?;
    let ident = identify(&mut inner, false).await.map_err(setup_sql)?;
    cp_proto(proto, "inner-after-write", Some(&ident)).map_err(Fail::Protocol)?;
    if kind == "conn-lost" {
        tokio::time::sleep(Duration::from_millis(settle_ms)).await;
    } else {
        shared.set_pid(ident.pid);
        *rx_slot = Some(match kind {
            "rejected" => shared.arm_savepoint_rewrite(),
            _ => shared.arm_savepoint_reject(),
        });
    }
    let app = "application error: the nested scope fails";
    if drops {
        drop(inner);
        nested.insert("caught".into(), json!(true));
        nested.insert("error".into(), app_error(app));
        return Ok(());
    }
    match inner.rollback().await {
        Ok(()) => {
            nested.insert("caught".into(), json!(true));
            nested.insert("error".into(), app_error(app));
        }
        Err(err) => {
            nested.insert("caught".into(), json!(true));
            nested.insert("error".into(), sql_error(&err));
        }
    }
    Ok(())
}

fn map_commit(result: Result<(), sqlx::Error>) -> Outcome {
    match result {
        Ok(()) => Outcome {
            reported: "committed".into(),
            basis: "Transaction::commit returned Ok".into(),
            api_error: None,
        },
        Err(err) => Outcome {
            reported: "failed".into(),
            basis: "Transaction::commit returned an error, which asserts neither commit nor rollback".into(),
            api_error: Some(sql_error(&err)),
        },
    }
}

fn map_explicit_rollback(result: Result<(), sqlx::Error>, app: &str) -> Outcome {
    match result {
        Ok(()) => Outcome {
            reported: "rolled_back".into(),
            basis: format!("the application raised an error and Transaction::rollback returned Ok ({app})"),
            api_error: Some(app_error(app)),
        },
        Err(err) => Outcome {
            reported: "failed".into(),
            basis: "Transaction::rollback returned an error, so the API did not report a completed rollback".into(),
            api_error: Some(sql_error(&err)),
        },
    }
}

fn rolled_back_drop(app: &str) -> Outcome {
    Outcome {
        reported: "rolled_back".into(),
        basis: "the Transaction was dropped while open. SQLx documents that rollback is called on drop. start_rollback only queues the statement and returns no result to the caller. The caller observed the application error.".into(),
        api_error: Some(app_error(app)),
    }
}

fn map_managed(result: Result<(), CaseError>, end: &Mutex<Option<CallbackEnd>>) -> Outcome {
    let recorded = end.lock().expect("callback").clone();
    match result {
        Ok(()) => Outcome {
            reported: "committed".into(),
            basis: "Connection::transaction returned Ok, so the callback returned Ok and commit returned Ok".into(),
            api_error: None,
        },
        Err(error) => {
            if recorded.as_ref().is_some_and(|item| item.protocol) || matches!(error, CaseError::Protocol(_)) {
                return Outcome {
                    reported: "failed".into(),
                    basis: "a protocol checkpoint failed inside Connection::transaction".into(),
                    api_error: Some(json!({"class": "protocol", "message": error.to_string()})),
                };
            }
            let same = recorded.as_ref().is_some_and(|item| item.message == error.to_string());
            if same {
                Outcome {
                    reported: "rolled_back".into(),
                    basis: "Connection::transaction returned the callback's error, so rollback returned Ok".into(),
                    api_error: recorded.map(|item| item.error),
                }
            } else {
                Outcome {
                    reported: "failed".into(),
                    basis: "Connection::transaction returned an error other than the callback's error. Commit or rollback failed, and a rollback error replaces the callback error.".into(),
                    api_error: Some(case_error_value(&error)),
                }
            }
        }
    }
}

fn callback_end(error: &CaseError) -> CallbackEnd {
    CallbackEnd {
        message: error.to_string(),
        error: case_error_value(error),
        protocol: matches!(error, CaseError::Protocol(_)),
    }
}

fn case_error_value(error: &CaseError) -> Value {
    match error {
        CaseError::App(message) => app_error(message),
        CaseError::Sql(err) => sql_error(err),
        CaseError::Protocol(message) => json!({"class": "protocol", "message": message}),
    }
}

fn outcome_json(outcome: &Outcome) -> Map<String, Value> {
    let mut body = Map::new();
    body.insert("reported".into(), json!(outcome.reported));
    body.insert("basis".into(), json!(outcome.basis));
    if let Some(error) = &outcome.api_error {
        body.insert("api_error".into(), error.clone());
    }
    body
}

async fn insert_marker(conn: &mut PgConnection, name: &str) -> Result<(), sqlx::Error> {
    sqlx::query("insert into item (name, qty) values ($1, 0)").bind(name).execute(conn).await?;
    Ok(())
}

async fn insert_taken(conn: &mut PgConnection) -> Result<(), sqlx::Error> {
    sqlx::query("insert into uniq (code) values ($1)").bind("taken").execute(conn).await?;
    Ok(())
}

async fn read_marker(conn: &mut PgConnection, name: &str) -> Result<(), sqlx::Error> {
    let (got,): (String,) = sqlx::query_as("select name from item where name = $1").bind(name).fetch_one(&mut *conn).await?;
    if got != name {
        return Err(sqlx::Error::Protocol("the marker read did not return the written value".into()));
    }
    Ok(())
}

async fn identify(conn: &mut PgConnection, isolation: bool) -> Result<Ident, sqlx::Error> {
    if isolation {
        let (xid, pid, level): (String, i32, String) = sqlx::query_as(
            "select pg_current_xact_id()::text, pg_backend_pid(), current_setting('transaction_isolation')",
        )
        .fetch_one(&mut *conn)
        .await?;
        Ok(Ident { xid, pid, isolation: Some(level) })
    } else {
        let (xid, pid): (String, i32) = sqlx::query_as("select pg_current_xact_id()::text, pg_backend_pid()")
            .fetch_one(&mut *conn)
            .await?;
        Ok(Ident { xid, pid, isolation: None })
    }
}

async fn set_isolation(conn: &mut PgConnection, level: &str) -> Result<(), sqlx::Error> {
    let sql = match level {
        "serializable" => "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE",
        "repeatable read" => "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ",
        "read committed" => "SET TRANSACTION ISOLATION LEVEL READ COMMITTED",
        "read uncommitted" => "SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED",
        _ => return Err(sqlx::Error::Protocol(format!("unknown isolation level {level}").into())),
    };
    sqlx::query(sql).execute(&mut *conn).await?;
    Ok(())
}

async fn plain_baseline(conn: &mut PgConnection, proto: &Protocol) -> Result<(), sqlx::Error> {
    let mut tx = Connection::begin(&mut *conn).await?;
    let ident = identify(&mut tx, false).await?;
    proto.checkpoint("baseline", Some(&ident.xid), Some(ident.pid), None).map_err(|err| sqlx::Error::Protocol(err.into()))?;
    tx.commit().await?;
    Ok(())
}

fn cp_proto(proto: &Protocol, name: &str, ident: Option<&Ident>) -> Result<(), String> {
    match ident {
        Some(ident) => proto.checkpoint(name, Some(&ident.xid), Some(ident.pid), ident.isolation.as_deref()),
        None => proto.checkpoint(name, None, None, None),
    }
}

fn sql_error(err: &sqlx::Error) -> Value {
    let mut body = Map::new();
    body.insert("class".into(), json!("sqlx::Error"));
    if let Some(code) = err.as_database_error().and_then(|db| db.code()) {
        body.insert("code".into(), json!(code.to_string()));
    }
    body.insert("message".into(), json!(err.to_string()));
    Value::Object(body)
}

fn sql_error_value(err: &sqlx::Error) -> Value {
    sql_error(err)
}

fn app_error(message: &str) -> Value {
    json!({"class": "application", "message": message})
}

fn setup_sql(err: sqlx::Error) -> Fail {
    Fail::Setup(err.to_string())
}

fn fail_text(err: Fail) -> String {
    match err {
        Fail::Protocol(message) | Fail::Setup(message) => message,
    }
}

fn redact(message: String, password: &str) -> String {
    if password.is_empty() { message } else { message.replace(password, "[redacted]") }
}

fn savepoint_form(mode: Mode) -> String {
    format!(
        "Outer begin and Transaction::begin for SAVEPOINT _sqlx_savepoint_N. Nested rollback is {}. {}",
        if mode.drops() { "Drop of the inner Transaction" } else { "Transaction::rollback" },
        "The savepoint is not an independent transaction."
    )
}

fn nested_form(mode: Mode) -> String {
    format!(
        "Outer {} and an inner Transaction::begin, which SQLx implements as SAVEPOINT _sqlx_savepoint_N. The outer insert is executed before the savepoint. The inner scope is not an independent transaction.",
        if mode == Mode::Managed { "Connection::transaction" } else { "Connection::begin" }
    )
}

fn isolation_form(explicit: bool) -> String {
    if explicit {
        "Connection::begin, then SET TRANSACTION ISOLATION LEVEL as the first statement, then Transaction::commit. begin takes no isolation argument.".into()
    } else {
        "Connection::transaction. The callback's first statement is SET TRANSACTION ISOLATION LEVEL. transaction takes no isolation argument.".into()
    }
}

