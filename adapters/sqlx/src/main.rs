//! PPCS adapter for SQLx 0.9 on PostgreSQL.
//!
//! One process runs one case. The runner speaks protocol version 1 on stdin
//! and stdout. SQLx connects through a cleartext proxy in this process so a
//! category C fault can withhold or rewrite ROLLBACK before PostgreSQL sees it.

mod cases;
mod protocol;
mod proxy;

use cases::{Case, ConnInfo, Done, Fail, Settings};
use protocol::Protocol;
use serde_json::{json, Map, Value};
use std::collections::HashMap;
use std::sync::Arc;

#[tokio::main]
async fn main() {
    let proto = Arc::new(Protocol::new());
    let message = match proto.read() {
        Ok(message) => message,
        Err(err) => {
            let _ = send_result(&proto, error_result(&err));
            return;
        }
    };
    if message.get("type").and_then(Value::as_str) != Some("case") {
        let _ = send_result(&proto, error_result("the first protocol message was not a case"));
        return;
    }
    let case = match parse_case(&message) {
        Ok(case) => case,
        Err(err) => {
            let _ = send_hello(&proto, "explicit", &Settings { pool_max: 1, settle_ms: 100, bound_ms: 5000, isolation: None });
            let _ = send_result(&proto, error_result(&err));
            return;
        }
    };
    if let Err(err) = send_hello(&proto, &case.mode, &case.settings) {
        let _ = send_result(&proto, error_result(&err));
        return;
    }
    let result = match cases::execute(case, Arc::clone(&proto)).await {
        Ok(done) => completed(done),
        Err(Fail::Protocol(message)) => error_result(&message),
        Err(Fail::Setup(message)) => error_result(&message),
    };
    let _ = send_result(&proto, result);
}

fn parse_case(message: &Value) -> Result<Case, String> {
    let case = message.get("case").ok_or("the case message has no case")?;
    let connection = message.get("connection").ok_or("the case message has no connection")?;
    let markers = object_strings(message.get("markers").ok_or("the case message has no markers")?)?;
    let settings_value = case.get("settings").cloned().unwrap_or_else(|| json!({}));
    Ok(Case {
        id: text(case, "id")?,
        mode: text(message, "mode")?,
        connection: ConnInfo {
            host: text(connection, "host")?,
            port: connection.get("port").and_then(Value::as_u64).ok_or("connection.port is not a number")? as u16,
            user: text(connection, "user")?,
            password: text(connection, "password")?,
            database: text(connection, "database")?,
            application_name: text(connection, "application_name")?,
        },
        markers,
        settings: Settings {
            pool_max: number(&settings_value, "pool_max").unwrap_or(1) as u32,
            settle_ms: number(&settings_value, "settle_ms").unwrap_or(100),
            bound_ms: number(&settings_value, "bound_ms").unwrap_or(5000),
            isolation: settings_value.get("isolation_level").and_then(Value::as_str).map(str::to_string),
        },
    })
}

fn send_hello(proto: &Protocol, mode: &str, settings: &Settings) -> Result<(), String> {
    let mut configuration = Map::new();
    configuration.insert("pool_max".into(), json!(settings.pool_max));
    configuration.insert("min_connections".into(), json!(0));
    configuration.insert("test_before_acquire".into(), json!(false));
    configuration.insert("sslmode".into(), json!("disable"));
    configuration.insert("statement_logging".into(), json!(false));
    configuration.insert("features".into(), json!(["runtime-tokio", "postgres"]));
    configuration.insert("compile_time_macros".into(), json!(false));
    configuration.insert("rollback".into(), json!(rollback_label(mode)));
    configuration.insert("connection".into(), json!(if mode == "direct" || mode == "direct-drop" { "PgConnection" } else { "PgPool" }));
    let mut body = Map::new();
    body.insert("type".into(), json!("hello"));
    body.insert("adapter".into(), json!({"name": "sqlx", "version": env!("CARGO_PKG_VERSION")}));
    body.insert("framework".into(), json!({"name": "sqlx", "version": env!("PPCS_SQLX_VERSION")}));
    body.insert("driver".into(), json!({"name": "sqlx-postgres", "version": env!("PPCS_SQLX_POSTGRES_VERSION")}));
    body.insert("components".into(), json!({
        "sqlx-core": env!("PPCS_SQLX_CORE_VERSION"),
        "tokio": env!("PPCS_TOKIO_VERSION"),
        "serde_json": env!("PPCS_SERDE_JSON_VERSION"),
    }));
    body.insert("runtime".into(), json!({"name": "rustc", "version": env!("PPCS_RUSTC")}));
    body.insert("mode".into(), json!(mode));
    body.insert("configuration".into(), Value::Object(configuration));
    proto.send(body)
}

fn rollback_label(mode: &str) -> &'static str {
    match mode {
        "managed" => "Connection::transaction calls Transaction::rollback",
        "drop" | "direct-drop" => "Transaction::drop queues start_rollback",
        "sql" => "Transaction::commit or Connection::transaction, with SET TRANSACTION first for TX-05",
        _ => "Transaction::commit and Transaction::rollback",
    }
}

fn completed(done: Done) -> Map<String, Value> {
    let mut body = Map::new();
    body.insert("type".into(), json!("result"));
    body.insert("status".into(), json!("completed"));
    body.insert("reported".into(), json!(done.reported));
    body.insert("basis".into(), json!(done.basis));
    body.insert("contract".into(), json!(done.contract));
    if let Some(error) = done.api_error {
        body.insert("api_error".into(), error);
    }
    body.insert("steps".into(), Value::Object(done.steps));
    if let Some(form) = done.form {
        body.insert("form".into(), json!(form));
    }
    body.insert("diagnostics".into(), done.diagnostics);
    body
}

fn error_result(message: &str) -> Map<String, Value> {
    let mut body = Map::new();
    body.insert("type".into(), json!("result"));
    body.insert("status".into(), json!("error"));
    body.insert("error".into(), json!({"class": "protocol", "message": message}));
    body
}

fn send_result(proto: &Protocol, body: Map<String, Value>) -> Result<(), String> {
    proto.send(body)
}

fn text(value: &Value, key: &str) -> Result<String, String> {
    value.get(key).and_then(Value::as_str).map(str::to_string).ok_or_else(|| format!("missing string field {key}"))
}

fn number(value: &Value, key: &str) -> Option<u64> {
    value.get(key).and_then(Value::as_u64)
}

fn object_strings(value: &Value) -> Result<HashMap<String, String>, String> {
    let object = value.as_object().ok_or("markers is not an object")?;
    let mut out = HashMap::new();
    for (key, item) in object {
        let text = item.as_str().ok_or_else(|| format!("marker {key} is not a string"))?;
        out.insert(key.clone(), text.to_string());
    }
    Ok(out)
}
