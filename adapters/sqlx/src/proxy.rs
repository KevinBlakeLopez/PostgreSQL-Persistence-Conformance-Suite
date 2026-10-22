//! Cleartext PostgreSQL proxy in this process.
//!
//! SQLx owns the socket, so a category C fault cannot be raised from a
//! `QueryTracer`. This proxy is the adapter's driver-side injection point:
//! a simple-query or Parse of `ROLLBACK` / `ROLLBACK TO` is withheld or
//! rewritten before the upstream server sees it. `after-fault` is reported
//! from here, before the bytes of the error are written back to SQLx.
//!
//! Every other message is forwarded. CommandComplete tags are recorded so a
//! later `COMMIT` can be compared with what `Transaction::commit` returns.
//! The proxy does not drop a COMMIT reply. Category E is the runner's proxy.

use crate::protocol::Protocol;
use std::sync::Arc;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::oneshot;

const SSL_REQUEST: i32 = 80877103;
const CLIENT_AUTH: [i32; 4] = [3, 5, 10, 11];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Armed {
    RootReject,
    SavepointReject,
    SavepointRewrite,
}

struct Taken {
    rewrite: bool,
    original_sql: String,
    pid: i32,
    done: oneshot::Sender<()>,
}

struct State {
    armed: Option<Armed>,
    fired: u32,
    mode: Option<&'static str>,
    reply_codes: Vec<String>,
    hook_error: Option<String>,
    withheld: Vec<String>,
    rewritten: Vec<String>,
    simple: Vec<String>,
    tags: Vec<String>,
    done: Option<oneshot::Sender<()>>,
    /// Backend pid captured before the fault is armed. `after-fault` reports it.
    pid: i32,
}

pub struct Shared {
    state: std::sync::Mutex<State>,
    protocol: Arc<Protocol>,
}

impl Shared {
    pub fn new(protocol: Arc<Protocol>) -> Arc<Self> {
        Arc::new(Self {
            state: std::sync::Mutex::new(State {
                armed: None,
                fired: 0,
                mode: None,
                reply_codes: Vec::new(),
                hook_error: None,
                withheld: Vec::new(),
                rewritten: Vec::new(),
                simple: Vec::new(),
                tags: Vec::new(),
                done: None,
                pid: 0,
            }),
            protocol,
        })
    }

    pub fn arm_root_reject(&self) -> oneshot::Receiver<()> {
        self.arm(Armed::RootReject, "client-reject")
    }

    pub fn arm_savepoint_reject(&self) -> oneshot::Receiver<()> {
        self.arm(Armed::SavepointReject, "client-reject")
    }

    pub fn arm_savepoint_rewrite(&self) -> oneshot::Receiver<()> {
        self.arm(Armed::SavepointRewrite, "rewrite")
    }

    fn arm(&self, kind: Armed, mode: &'static str) -> oneshot::Receiver<()> {
        let (tx, rx) = oneshot::channel();
        let mut state = self.state.lock().expect("fault lock");
        state.armed = Some(kind);
        state.mode = Some(mode);
        state.done = Some(tx);
        rx
    }

    pub fn set_pid(&self, pid: i32) {
        self.state.lock().expect("fault lock").pid = pid;
    }

    pub fn report(&self) -> serde_json::Value {
        let state = self.state.lock().expect("fault lock");
        let mut body = serde_json::Map::new();
        if let Some(mode) = state.mode {
            body.insert("mode".into(), serde_json::json!(mode));
        }
        body.insert("fired".into(), serde_json::json!(state.fired));
        if state.mode == Some("rewrite") {
            body.insert("reply_codes".into(), serde_json::json!(state.reply_codes));
        }
        if let Some(hook) = &state.hook_error {
            body.insert("hook_error".into(), serde_json::json!(hook));
        }
        serde_json::Value::Object(body)
    }

    pub fn trace(&self) -> serde_json::Value {
        let state = self.state.lock().expect("fault lock");
        serde_json::json!({
            "simple_queries": state.simple,
            "command_tags": state.tags,
            "withheld": state.withheld,
            "rewritten": state.rewritten,
        })
    }

    fn note_simple(&self, sql: &str) {
        let mut state = self.state.lock().expect("fault lock");
        if state.simple.len() < 80 {
            state.simple.push(truncate(sql));
        }
    }

    fn note_tags(&self, tags: &[String]) {
        let mut state = self.state.lock().expect("fault lock");
        for tag in tags {
            if state.tags.len() < 80 {
                state.tags.push(tag.clone());
            }
        }
    }

    fn take(&self, sql: &str) -> Option<Taken> {
        let mut state = self.state.lock().expect("fault lock");
        let kind = state.armed?;
        let matches = match kind {
            Armed::RootReject => is_root_rollback(sql),
            Armed::SavepointReject | Armed::SavepointRewrite => is_rollback_to(sql),
        };
        if !matches {
            return None;
        }
        state.armed = None;
        state.fired += 1;
        let done = state.done.take()?;
        let pid = state.pid;
        Some(Taken {
            rewrite: kind == Armed::SavepointRewrite,
            original_sql: sql.to_string(),
            pid,
            done,
        })
    }

    fn note_withheld(&self, sql: &str) {
        self.state.lock().expect("fault lock").withheld.push(truncate(sql));
    }

    fn note_rewrite(&self, sql: &str, codes: &[String]) {
        let mut state = self.state.lock().expect("fault lock");
        state.rewritten.push(truncate(sql));
        state.reply_codes.extend(codes.iter().cloned());
    }

    fn note_hook(&self, error: String) {
        self.state.lock().expect("fault lock").hook_error = Some(error);
    }
}


pub struct Proxy {
    port: u16,
    accept: tokio::task::JoinHandle<()>,
}

impl Proxy {
    pub async fn start(upstream_host: String, upstream_port: u16, shared: Arc<Shared>) -> std::io::Result<Self> {
        let listener = TcpListener::bind("127.0.0.1:0").await?;
        let port = listener.local_addr()?.port();
        let accept = tokio::spawn(async move {
            loop {
                let Ok((client, _)) = listener.accept().await else { break };
                let host = upstream_host.clone();
                let shared = Arc::clone(&shared);
                tokio::spawn(async move {
                    if let Err(err) = session(client, &host, upstream_port, shared).await {
                        eprintln!("sqlx-proxy: session ended: {err}");
                    }
                });
            }
        });
        Ok(Self { port, accept })
    }

    pub fn port(&self) -> u16 {
        self.port
    }
}

impl Drop for Proxy {
    fn drop(&mut self) {
        self.accept.abort();
    }
}

async fn session(mut client: TcpStream, host: &str, port: u16, shared: Arc<Shared>) -> std::io::Result<()> {
    let _ = client.set_nodelay(true);
    let mut upstream = TcpStream::connect((host, port)).await?;
    let _ = upstream.set_nodelay(true);
    if forward_startup(&mut client, &mut upstream).await? == Startup::Ssl {
        return Err(std::io::Error::other("the SQLx proxy requires a cleartext connection"));
    }
    forward_auth(&mut client, &mut upstream).await?;
    let mut tx_status = b'I';
    loop {
        let msg = read_message(&mut client).await?;
        if msg.type_ == b'X' {
            let _ = upstream.write_all(&msg.raw).await;
            return Ok(());
        }
        if msg.type_ == b'Q' {
            let sql = query_sql(&msg.payload);
            shared.note_simple(&sql);
            if let Some(taken) = shared.take(&sql) {
                if taken.rewrite {
                    let rewritten = "ROLLBACK TO SAVEPOINT ppcs_no_such_savepoint";
                    let out = build_query(rewritten);
                    upstream.write_all(&out).await?;
                    let response = read_until_ready(&mut upstream).await?;
                    tx_status = response.status;
                    let codes = error_codes(&response.bytes);
                    shared.note_rewrite(rewritten, &codes);
                    shared.note_tags(&response.tags);
                    finish_fault(&shared, taken).await;
                    client.write_all(&response.bytes).await?;
                } else {
                    shared.note_withheld(&taken.original_sql);
                    finish_fault(&shared, taken).await;
                    client.write_all(&error_and_ready(tx_status, "injected client-side failure: statement was not sent")).await?;
                }
                continue;
            }
            upstream.write_all(&msg.raw).await?;
            let response = read_until_ready(&mut upstream).await?;
            tx_status = response.status;
            shared.note_tags(&response.tags);
            if response.tags.iter().any(|t| t == "COMMIT" || t == "ROLLBACK") {
                eprintln!("sqlx-proxy: {sql} -> {}", response.tags.join(","));
            }
            client.write_all(&response.bytes).await?;
            continue;
        }
        if msg.type_ == b'P' {
            if let Some(sql) = parse_sql(&msg.payload) {
                if is_root_rollback(&sql) || is_rollback_to(&sql) {
                    // PgTransactionManager sends ROLLBACK as a simple query. An extended
                    // ROLLBACK would not be withheld by the 'Q' path above.
                    eprintln!("sqlx-proxy: extended transaction statement was not intercepted: {sql}");
                }
            }
        }
        let mut pending = Vec::new();
        if let Some(kind) = expect_kind(msg.type_, &msg.payload) {
            pending.push(kind);
        }
        upstream.write_all(&msg.raw).await?;
        let sync = msg.type_ == b'S';
        let flush = msg.type_ == b'H';
        if !sync && !flush {
            // More of a pipeline may already be buffered. Keep reading until Sync or Flush.
            // A single non-terminal message has been forwarded. Loop.
            // Parse/Bind/Execute/Describe are accumulated across iterations via `pending` only
            // within this message. The server does not reply until Sync or Flush, so the next
            // client message is read by the outer loop. Pending replies are tracked here only
            // for this message, which is wrong for a pipeline.
            //
            // The loop below reads ahead until Sync or Flush so one pipeline is one response.
            let response = read_pipeline(&mut client, &mut upstream, pending, &shared).await?;
            if let Some(status) = response.status {
                tx_status = status;
            }
            shared.note_tags(&response.tags);
            if !response.bytes.is_empty() {
                client.write_all(&response.bytes).await?;
            }
            if response.terminated {
                return Ok(());
            }
        } else {
            let response = read_pending(&mut upstream, &pending, sync).await?;
            if let Some(status) = response.status {
                tx_status = status;
            }
            shared.note_tags(&response.tags);
            if !response.bytes.is_empty() {
                client.write_all(&response.bytes).await?;
            }
        }
    }
}

/// Read client messages until Flush or Sync, forwarding them, then read the server reply.
async fn read_pipeline(
    client: &mut TcpStream,
    upstream: &mut TcpStream,
    mut pending: Vec<Kind>,
    shared: &Shared,
) -> std::io::Result<PipeEnd> {
    loop {
        let msg = read_message(client).await?;
        if msg.type_ == b'X' {
            let _ = upstream.write_all(&msg.raw).await;
            return Ok(PipeEnd { bytes: Vec::new(), status: None, tags: Vec::new(), terminated: true });
        }
        if msg.type_ == b'Q' {
            // A simple query ends the extended pipeline. Handle it as its own exchange.
            upstream.write_all(&msg.raw).await?;
            let sql = query_sql(&msg.payload);
            shared.note_simple(&sql);
            let response = read_until_ready(upstream).await?;
            shared.note_tags(&response.tags);
            return Ok(PipeEnd {
                bytes: response.bytes,
                status: Some(response.status),
                tags: response.tags,
                terminated: false,
            });
        }
        if let Some(kind) = expect_kind(msg.type_, &msg.payload) {
            pending.push(kind);
        }
        upstream.write_all(&msg.raw).await?;
        let sync = msg.type_ == b'S';
        let flush = msg.type_ == b'H';
        if sync || flush {
            let response = read_pending(upstream, &pending, sync).await?;
            return Ok(PipeEnd {
                bytes: response.bytes,
                status: response.status,
                tags: response.tags,
                terminated: false,
            });
        }
    }
}

struct PipeEnd {
    bytes: Vec<u8>,
    status: Option<u8>,
    tags: Vec<String>,
    terminated: bool,
}

async fn finish_fault(shared: &Shared, taken: Taken) {
    if let Err(err) = shared.protocol.checkpoint("after-fault", None, Some(taken.pid), None) {
        shared.note_hook(err);
    }
    let _ = taken.done.send(());
}

#[derive(Clone, Copy)]
enum Kind {
    Parse,
    Bind,
    Execute,
    Close,
    DescribeStatement,
    DescribePortal,
}

fn expect_kind(type_: u8, payload: &[u8]) -> Option<Kind> {
    Some(match type_ {
        b'P' => Kind::Parse,
        b'B' => Kind::Bind,
        b'E' => Kind::Execute,
        b'C' => Kind::Close,
        b'D' => {
            if payload.first() == Some(&b'S') {
                Kind::DescribeStatement
            } else {
                Kind::DescribePortal
            }
        }
        _ => return None,
    })
}

fn step_for(kind: Kind, type_: u8) -> Step {
    if type_ == b'N' || type_ == b'S' || type_ == b'A' {
        return Step::Skip;
    }
    if type_ == b'E' {
        return Step::Error;
    }
    match (kind, type_) {
        (Kind::Parse, b'1') => Step::Done,
        (Kind::Bind, b'2') => Step::Done,
        (Kind::Close, b'3') => Step::Done,
        (Kind::DescribeStatement, b't') => Step::More,
        (Kind::DescribeStatement | Kind::DescribePortal, b'T' | b'n') => Step::Done,
        (Kind::Execute, b'T' | b'D') => Step::More,
        (Kind::Execute, b'C' | b'I' | b's') => Step::Done,
        _ => Step::Bad,
    }
}

enum Step {
    Skip,
    More,
    Done,
    Error,
    Bad,
}

struct ReadyBytes {
    bytes: Vec<u8>,
    status: u8,
    tags: Vec<String>,
}

async fn read_until_ready(stream: &mut TcpStream) -> std::io::Result<ReadyBytes> {
    let mut bytes = Vec::new();
    let mut tags = Vec::new();
    loop {
        let msg = read_message(stream).await?;
        if msg.type_ == b'C' {
            tags.push(command_tag(&msg.payload));
        }
        if msg.type_ == b'Z' {
            let status = *msg.payload.first().unwrap_or(&b'I');
            bytes.extend_from_slice(&msg.raw);
            return Ok(ReadyBytes { bytes, status, tags });
        }
        bytes.extend_from_slice(&msg.raw);
    }
}

struct PendingBytes {
    bytes: Vec<u8>,
    status: Option<u8>,
    tags: Vec<String>,
}

async fn read_pending(stream: &mut TcpStream, pending: &[Kind], sync: bool) -> std::io::Result<PendingBytes> {
    let mut bytes = Vec::new();
    let mut tags = Vec::new();
    let mut index = 0;
    while index < pending.len() {
        let msg = read_message(stream).await?;
        bytes.extend_from_slice(&msg.raw);
        if msg.type_ == b'C' {
            tags.push(command_tag(&msg.payload));
        }
        match step_for(pending[index], msg.type_) {
            Step::Skip | Step::More => continue,
            Step::Done => index += 1,
            Step::Error => {
                if sync {
                    let rest = read_until_ready(stream).await?;
                    bytes.extend_from_slice(&rest.bytes);
                    tags.extend(rest.tags);
                    return Ok(PendingBytes { bytes, status: Some(rest.status), tags });
                }
                return Ok(PendingBytes { bytes, status: None, tags });
            }
            Step::Bad => {
                return Err(std::io::Error::other(format!(
                    "unexpected server message {} for extended reply {index}",
                    msg.type_ as char
                )));
            }
        }
    }
    if sync {
        let rest = read_until_ready(stream).await?;
        bytes.extend_from_slice(&rest.bytes);
        tags.extend(rest.tags);
        return Ok(PendingBytes { bytes, status: Some(rest.status), tags });
    }
    Ok(PendingBytes { bytes, status: None, tags })
}

#[derive(PartialEq, Eq)]
enum Startup {
    Clear,
    Ssl,
}

async fn forward_startup(client: &mut TcpStream, upstream: &mut TcpStream) -> std::io::Result<Startup> {
    let mut head = [0u8; 8];
    client.read_exact(&mut head).await?;
    let len = i32::from_be_bytes([head[0], head[1], head[2], head[3]]);
    let code = i32::from_be_bytes([head[4], head[5], head[6], head[7]]);
    if len == 8 && code == SSL_REQUEST {
        upstream.write_all(&head).await?;
        let mut answer = [0u8; 1];
        upstream.read_exact(&mut answer).await?;
        client.write_all(&answer).await?;
        if answer[0] == b'S' {
            return Ok(Startup::Ssl);
        }
        let mut len_buf = [0u8; 4];
        client.read_exact(&mut len_buf).await?;
        let startup_len = i32::from_be_bytes(len_buf) as usize;
        if startup_len < 4 {
            return Err(std::io::Error::other("bad startup length"));
        }
        let mut rest = vec![0u8; startup_len - 4];
        client.read_exact(&mut rest).await?;
        upstream.write_all(&len_buf).await?;
        upstream.write_all(&rest).await?;
        return Ok(Startup::Clear);
    }
    if len < 8 {
        return Err(std::io::Error::other("bad startup length"));
    }
    let mut rest = vec![0u8; len as usize - 8];
    client.read_exact(&mut rest).await?;
    upstream.write_all(&head).await?;
    upstream.write_all(&rest).await?;
    Ok(Startup::Clear)
}

async fn forward_auth(client: &mut TcpStream, upstream: &mut TcpStream) -> std::io::Result<()> {
    loop {
        let msg = read_message(upstream).await?;
        let auth_code = if msg.type_ == b'R' && msg.payload.len() >= 4 {
            Some(i32::from_be_bytes([msg.payload[0], msg.payload[1], msg.payload[2], msg.payload[3]]))
        } else {
            None
        };
        client.write_all(&msg.raw).await?;
        if msg.type_ == b'Z' {
            return Ok(());
        }
        if msg.type_ == b'R' && auth_code.is_some_and(|c| CLIENT_AUTH.contains(&c)) {
            let reply = read_message(client).await?;
            upstream.write_all(&reply.raw).await?;
        }
    }
}

struct Message {
    type_: u8,
    payload: Vec<u8>,
    raw: Vec<u8>,
}

async fn read_message(stream: &mut TcpStream) -> std::io::Result<Message> {
    let mut head = [0u8; 5];
    stream.read_exact(&mut head).await?;
    let len = u32::from_be_bytes([head[1], head[2], head[3], head[4]]) as usize;
    if len < 4 {
        return Err(std::io::Error::other(format!("bad message length {len}")));
    }
    let mut payload = vec![0u8; len - 4];
    stream.read_exact(&mut payload).await?;
    let mut raw = Vec::with_capacity(1 + len);
    raw.extend_from_slice(&head);
    raw.extend_from_slice(&payload);
    Ok(Message { type_: head[0], payload, raw })
}

fn query_sql(payload: &[u8]) -> String {
    cstr(payload).map(|(s, _)| s.to_string()).unwrap_or_default()
}

fn parse_sql(payload: &[u8]) -> Option<String> {
    let (_, rest) = cstr(payload)?;
    let (sql, _) = cstr(rest)?;
    Some(sql.to_string())
}

fn cstr(buf: &[u8]) -> Option<(&str, &[u8])> {
    let end = buf.iter().position(|b| *b == 0)?;
    let s = std::str::from_utf8(&buf[..end]).ok()?;
    Some((s, &buf[end + 1..]))
}

fn command_tag(payload: &[u8]) -> String {
    cstr(payload).map(|(s, _)| s.to_string()).unwrap_or_default()
}

fn build_query(sql: &str) -> Vec<u8> {
    let n = 4 + sql.len() + 1;
    let mut buf = Vec::with_capacity(1 + n);
    buf.push(b'Q');
    buf.extend_from_slice(&(n as u32).to_be_bytes());
    buf.extend_from_slice(sql.as_bytes());
    buf.push(0);
    buf
}

fn error_and_ready(status: u8, message: &str) -> Vec<u8> {
    let mut payload = Vec::new();
    for (tag, val) in [(b'S', "ERROR"), (b'V', "ERROR"), (b'C', "XX000"), (b'M', message)] {
        payload.push(tag);
        payload.extend_from_slice(val.as_bytes());
        payload.push(0);
    }
    payload.push(0);
    let mut out = Vec::new();
    out.push(b'E');
    out.extend_from_slice(&((4 + payload.len()) as u32).to_be_bytes());
    out.extend_from_slice(&payload);
    out.push(b'Z');
    out.extend_from_slice(&5u32.to_be_bytes());
    out.push(status);
    out
}

fn error_codes(bytes: &[u8]) -> Vec<String> {
    let mut codes = Vec::new();
    let mut offset = 0;
    while offset + 5 <= bytes.len() {
        let type_ = bytes[offset];
        let len = u32::from_be_bytes([bytes[offset + 1], bytes[offset + 2], bytes[offset + 3], bytes[offset + 4]]) as usize;
        if len < 4 || offset + 1 + len > bytes.len() {
            break;
        }
        if type_ == b'E' {
            let payload = &bytes[offset + 5..offset + 1 + len];
            if let Some(code) = field(payload, b'C') {
                codes.push(code);
            } else {
                codes.push("error".to_string());
            }
        }
        offset += 1 + len;
    }
    codes
}

fn field(payload: &[u8], want: u8) -> Option<String> {
    let mut i = 0;
    while i < payload.len() {
        let tag = payload[i];
        if tag == 0 {
            break;
        }
        let start = i + 1;
        let end = payload[start..].iter().position(|b| *b == 0)? + start;
        if tag == want {
            return Some(String::from_utf8_lossy(&payload[start..end]).into_owned());
        }
        i = end + 1;
    }
    None
}

fn truncate(sql: &str) -> String {
    let mut one = sql.split_whitespace().collect::<Vec<_>>().join(" ");
    if one.len() > 180 {
        one.truncate(180);
    }
    one
}

pub fn is_rollback_to(sql: &str) -> bool {
    norm(sql).starts_with("rollback to")
}

pub fn is_root_rollback(sql: &str) -> bool {
    let s = norm(sql);
    s == "rollback" || (s.starts_with("rollback ") && !s.starts_with("rollback to"))
}

fn norm(sql: &str) -> String {
    sql.trim().trim_end_matches(';').trim().split_whitespace().collect::<Vec<_>>().join(" ").to_ascii_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rollback_match_does_not_confuse_savepoints() {
        assert!(is_root_rollback("ROLLBACK"));
        assert!(is_root_rollback("rollback;"));
        assert!(!is_root_rollback("ROLLBACK TO SAVEPOINT _sqlx_savepoint_1"));
        assert!(is_rollback_to("ROLLBACK TO SAVEPOINT _sqlx_savepoint_1"));
        assert!(is_rollback_to("rollback to sp"));
        assert!(!is_rollback_to("ROLLBACK"));
        assert!(!is_root_rollback("COMMIT"));
    }

    #[test]
    fn query_message_round_trip() {
        let msg = build_query("ROLLBACK");
        assert_eq!(msg[0], b'Q');
        let len = u32::from_be_bytes([msg[1], msg[2], msg[3], msg[4]]) as usize;
        assert_eq!(len, msg.len() - 1);
        assert_eq!(query_sql(&msg[5..]), "ROLLBACK");
    }

    #[test]
    fn error_response_carries_sqlstate_and_ready() {
        let bytes = error_and_ready(b'T', "injected client-side failure: statement was not sent");
        assert_eq!(bytes[0], b'E');
        let codes = error_codes(&bytes);
        assert_eq!(codes, vec!["XX000".to_string()]);
        assert_eq!(*bytes.last().unwrap(), b'T');
    }
}
