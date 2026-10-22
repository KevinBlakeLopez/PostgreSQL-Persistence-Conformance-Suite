//! PPCS adapter protocol version 1. stdout is the protocol stream.
//! A non-protocol line is not written here. Diagnostics go to stderr.

use serde_json::{json, Map, Value};
use std::io::{BufRead, BufReader, Stdin, Stdout, Write};
use std::sync::Mutex;

const PPCS: i64 = 1;

pub struct Protocol {
    inner: Mutex<Inner>,
}

struct Inner {
    stdin: BufReader<Stdin>,
    stdout: Stdout,
}

impl Protocol {
    pub fn new() -> Self {
        Self {
            inner: Mutex::new(Inner {
                stdin: BufReader::new(std::io::stdin()),
                stdout: std::io::stdout(),
            }),
        }
    }

    pub fn read(&self) -> Result<Value, String> {
        let mut inner = self.lock()?;
        inner.read_message()
    }

    pub fn send(&self, mut body: Map<String, Value>) -> Result<(), String> {
        body.insert("ppcs".into(), json!(PPCS));
        let mut inner = self.lock()?;
        inner.write_json(&Value::Object(body))
    }

    pub fn checkpoint(
        &self,
        name: &str,
        xid: Option<&str>,
        pid: Option<i32>,
        isolation: Option<&str>,
    ) -> Result<(), String> {
        let mut body = Map::new();
        body.insert("type".into(), json!("checkpoint"));
        body.insert("name".into(), json!(name));
        if let Some(xid) = xid {
            body.insert("xid".into(), json!(xid));
        }
        if let Some(pid) = pid {
            body.insert("pid".into(), json!(pid));
        }
        if let Some(isolation) = isolation {
            body.insert("transaction_isolation".into(), json!(isolation));
        }
        body.insert("ppcs".into(), json!(PPCS));
        let mut inner = self.lock()?;
        inner.write_json(&Value::Object(body))?;
        let msg = inner.read_message()?;
        let got_type = msg.get("type").and_then(Value::as_str);
        let got_name = msg.get("name").and_then(Value::as_str);
        if got_type != Some("resume") || got_name != Some(name) {
            return Err(format!("expected resume for checkpoint \"{name}\", got {msg}"));
        }
        Ok(())
    }

    fn lock(&self) -> Result<std::sync::MutexGuard<'_, Inner>, String> {
        self.inner.lock().map_err(|_| "the protocol lock was poisoned".to_string())
    }
}

impl Inner {
    fn write_json(&mut self, value: &Value) -> Result<(), String> {
        serde_json::to_writer(&mut self.stdout, value).map_err(|e| e.to_string())?;
        self.stdout.write_all(b"\n").map_err(|e| e.to_string())?;
        self.stdout.flush().map_err(|e| e.to_string())
    }

    fn read_message(&mut self) -> Result<Value, String> {
        loop {
            let mut line = String::new();
            let n = self.stdin.read_line(&mut line).map_err(|e| e.to_string())?;
            if n == 0 {
                return Err("the runner closed the protocol stream".to_string());
            }
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            let Ok(msg) = serde_json::from_str::<Value>(line) else {
                continue;
            };
            if msg.get("ppcs") == Some(&json!(PPCS)) {
                return Ok(msg);
            }
        }
    }
}
