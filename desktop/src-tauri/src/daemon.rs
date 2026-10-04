use std::process::{ExitStatus, Stdio};
use std::sync::Arc;
use std::time::Duration;
use tauri::async_runtime::Mutex;
use tokio::process::{Child, Command};
use tokio::time::timeout;

#[derive(Clone, Debug)]
pub struct DaemonHandle {
    pub base_url: String,
    child: Arc<Mutex<Option<Child>>>,
    stopping: Arc<Mutex<bool>>,
}

impl DaemonHandle {
    pub fn new(base_url: String) -> Self {
        Self {
            base_url,
            child: Arc::new(Mutex::new(None)),
            stopping: Arc::new(Mutex::new(false)),
        }
    }

    /// Start the Hi-EV Python daemon.
    pub async fn start(&self, python_bin: String, working_dir: String) -> Result<(), String> {
        let mut lock = self.child.lock().await;
        if lock.is_some() {
            return Err("Daemon already running".to_string());
        }

        // Reset the intentional-stop flag so a crash monitor can distinguish
        // a deliberate stop from an unexpected exit.
        *self.stopping.lock().await = false;

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

    /// Wait for the daemon process to exit and return its exit status.
    /// Returns `None` if no daemon was tracked or if the wait timed out.
    pub async fn wait_for_exit(&self) -> Option<ExitStatus> {
        let mut lock = self.child.lock().await;
        if let Some(child) = lock.as_mut() {
            let result = match timeout(Duration::from_secs(60), child.wait()).await {
                Ok(Ok(status)) => Some(status),
                _ => None,
            };
            // Once the process has exited, clear the tracked child so is_running is accurate.
            if result.is_some() {
                let _ = lock.take();
            }
            return result;
        }
        None
    }

    /// Stop the daemon gracefully, falling back to kill after a timeout.
    pub async fn stop(&self) -> Result<(), String> {
        *self.stopping.lock().await = true;
        let mut lock = self.child.lock().await;
        if let Some(mut child) = lock.take() {
            let _ = child.start_kill();
            let _ = timeout(Duration::from_secs(5), child.wait()).await;
        }
        Ok(())
    }

    /// Return whether the last stop was intentional.
    pub async fn was_intentional_stop(&self) -> bool {
        *self.stopping.lock().await
    }
}
