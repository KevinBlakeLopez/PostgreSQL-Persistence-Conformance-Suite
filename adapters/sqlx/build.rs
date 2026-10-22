use std::fs;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=Cargo.lock");
    emit_cmd("PPCS_RUSTC", "rustc", &["--version"]);
    emit_cmd("PPCS_CARGO", "cargo", &["--version"]);
    let lock = fs::read_to_string("Cargo.lock").unwrap_or_default();
    for (env, name) in [
        ("PPCS_SQLX_VERSION", "sqlx"),
        ("PPCS_SQLX_POSTGRES_VERSION", "sqlx-postgres"),
        ("PPCS_SQLX_CORE_VERSION", "sqlx-core"),
        ("PPCS_TOKIO_VERSION", "tokio"),
        ("PPCS_SERDE_JSON_VERSION", "serde_json"),
    ] {
        println!("cargo:rustc-env={env}={}", package_version(&lock, name));
    }
}

fn emit_cmd(env: &str, cmd: &str, args: &[&str]) {
    let text = std::process::Command::new(cmd)
        .args(args)
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|| "unknown".to_string());
    println!("cargo:rustc-env={env}={text}");
}

fn package_version(lock: &str, name: &str) -> String {
    let needle = format!("name = \"{name}\"");
    for package in lock.split("[[package]]").skip(1) {
        let mut lines = package.lines().map(str::trim);
        if lines.next() == Some(needle.as_str()) {
            if let Some(version) = lines.next().and_then(|l| l.strip_prefix("version = \"")) {
                if let Some(version) = version.strip_suffix('"') {
                    return version.to_string();
                }
            }
        }
    }
    "unknown".to_string()
}
