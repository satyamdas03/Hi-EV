pub mod daemon;
pub mod shortcut;
pub mod tray;

use std::time::Duration;

use tauri::{Manager, RunEvent};
use tauri_plugin_notification::NotificationExt;

use daemon::DaemonHandle;
use shortcut::{register_global_shortcut, shortcut_string};
use tray::build_tray;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(DaemonHandle::new("http://127.0.0.1:7345".to_string()))
        .setup(|app| {
            build_tray(app.handle())?;
            register_global_shortcut(app.handle())?;

            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let daemon = handle.state::<DaemonHandle>().inner().clone();
                let python_bin = std::env::var("EV_PYTHON_BIN").unwrap_or_else(|_| "python".to_string());
                let working_dir = std::env::var("EV_WORKING_DIR").unwrap_or_else(|_| ".".to_string());

                match daemon.start(python_bin, working_dir).await {
                    Ok(_) => {
                        match daemon.wait_for_health(45).await {
                            Ok(_) => {
                                let _ = handle.notification().builder()
                                    .title("Hi-EV is ready")
                                    .body(format!(
                                        "Press {} to talk to EV, or open the window from the tray.",
                                        shortcut_string()
                                    ))
                                    .show();
                                if let Some(window) = handle.get_webview_window("main") {
                                    let _ = window.show();
                                }
                            }
                            Err(e) => {
                                let _ = handle.notification().builder()
                                    .title("Hi-EV daemon is not responding")
                                    .body(format!("The background daemon did not become healthy: {e}"))
                                    .show();
                                eprintln!("Daemon did not become healthy: {e}");
                            }
                        }
                    }
                    Err(e) => {
                        let _ = handle.notification().builder()
                            .title("Hi-EV daemon failed to start")
                            .body(format!("Could not start the background daemon: {e}"))
                            .show();
                        eprintln!("Failed to start daemon: {e}");
                    }
                }
            });

            // Monitor the daemon process and notify the user if it exits unexpectedly.
            let monitor_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let daemon = monitor_handle.state::<DaemonHandle>().inner().clone();
                loop {
                    // Wait until a daemon process is tracked, then wait for it to exit.
                    if !daemon.is_running().await {
                        tokio::time::sleep(Duration::from_secs(1)).await;
                        continue;
                    }
                    let status = daemon.wait_for_exit().await;
                    if let Some(status) = status {
                        if !daemon.was_intentional_stop().await {
                            let body = if let Some(code) = status.code() {
                                format!("The background daemon exited unexpectedly (code {code}). Use the tray menu to restart it.")
                            } else {
                                "The background daemon exited unexpectedly. Use the tray menu to restart it.".to_string()
                            };
                            let _ = monitor_handle.notification().builder()
                                .title("Hi-EV daemon stopped")
                                .body(body)
                                .show();
                        }
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|_window, event| {
            // Hide to tray instead of closing on macOS / Linux window close.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                #[cfg(not(target_os = "windows"))]
                {
                    let _ = _window.hide();
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("Failed to build Tauri app")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                // Stop the daemon cleanly when the app exits.
                let handle = app_handle.state::<DaemonHandle>().inner().clone();
                tauri::async_runtime::block_on(async {
                    let _ = handle.stop().await;
                });
            }
        });
}
