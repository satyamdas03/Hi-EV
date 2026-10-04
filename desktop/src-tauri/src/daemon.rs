use std::process::Stdio;
use std::sync::Arc;
use std::time::Duration;
use tauri::async_runtime::Mutex;
use tokio::process::{Child, Command};
use tokio::time::timeout;

#[derive(Clone, Debug)]
pub struct DaemonHandle {
    pub base_url: String,
    child: Arc<Mutex<Option<Child>>>,
}

impl DaemonHandle {
    pub fn new(base_url: String) -> Self {
        Self {
            base_url,
            child: Arc::new(Mutex::new(None)),
        }
    }

    /// Start the Hi-EV Python daemon.
    pub async fn start(&self, python_bin: String, working_dir: String) -> Result<(), String> {
        let mut lock = self.child.lock().await;
        if lock.is_some() {
            return Err("Daemon already running".to_string());
        }

        let mut cmd = Command::new(&python_bin);
        cmd.arg("-m")
            .arg("evd")
            .current_dir(&working_dir)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        let child = cmd.spawn().map_err(|e| format!("Failed to spawn daemon: {e}"))?;
        *lock = Some(child);
        Ok(())
    }

    /// Poll /health until the daemon responds or the deadline elapses.
    pub async fn wait_for_health(&self, deadline_secs: u64) -> Result<(), String> {
        let url = format!("{}/health", self.base_url);
        let deadline = Duration::from_secs(deadline_secs);
        let start = tokio::time::Instant::now();

        loop {
            if start.elapsed() > deadline {
                return Err("Daemon health check timed out".to_string());
            }

            match reqwest::get(&url).await {
                Ok(resp) if resp.status().is_success() => return Ok(()),
                _ => tokio::time::sleep(Duration::from_millis(250)).await,
            }
        }
    }

    /// Return whether the daemon child process is currently tracked.
    pub async fn is_running(&self) -> bool {
        let lock = self.child.lock().await;
        lock.is_some()
    }

    /// Stop the daemon gracefully, falling back to kill after a timeout.
    pub async fn stop(&self) -> Result<(), String> {
        let mut lock = self.child.lock().await;
        if let Some(mut child) = lock.take() {
            let _ = child.start_kill();
            let _ = timeout(Duration::from_secs(5), child.wait()).await;
        }
        Ok(())
    }
}
