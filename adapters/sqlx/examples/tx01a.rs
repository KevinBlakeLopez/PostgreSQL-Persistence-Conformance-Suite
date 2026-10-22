//! Caught unique violation, then Transaction::commit.
//!
//! Uses the disposable database only. The harness case
//! TX-01A.caught-error-then-commit is the recorded run.

use sqlx::postgres::PgPoolOptions;
use sqlx::postgres::PgSslMode;
use sqlx::ConnectOptions;
use sqlx::PgPool;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = std::env::var("DATABASE_URL")?;
    let opts = url.parse::<sqlx::postgres::PgConnectOptions>()?.ssl_mode(PgSslMode::Disable).disable_statement_logging();
    let pool = PgPoolOptions::new().max_connections(1).min_connections(0).connect_with(opts).await?;
    let mut tx = pool.begin().await?;
    sqlx::query("insert into uniq (code) values ($1)").bind("ppcs-tx01a").execute(&mut *tx).await?;
    let duplicate = sqlx::query("insert into uniq (code) values ($1)").bind("taken").execute(&mut *tx).await;
    let state = duplicate.as_ref().err().and_then(|err| err.as_database_error()).and_then(|err| err.code().map(|code| code.to_string()));
    eprintln!("duplicate_sqlstate={}", state.unwrap_or_else(|| "none".into()));
    let committed = tx.commit().await;
    match &committed {
        Ok(()) => eprintln!("commit=ok"),
        Err(err) => eprintln!("commit=err {err}"),
    }
    let check = PgPool::connect_with(url.parse::<sqlx::postgres::PgConnectOptions>()?.ssl_mode(PgSslMode::Disable)).await?;
    let (present,): (bool,) = sqlx::query_as("select exists(select 1 from uniq where code = $1)")
        .bind("ppcs-tx01a")
        .fetch_one(&check)
        .await?;
    eprintln!("row_visible={present}");
    check.close().await;
    Ok(())
}
