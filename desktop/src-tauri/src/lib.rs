pub mod daemon;
pub mod shortcut;
pub mod tray;

use tauri::{Manager, RunEvent};

use daemon::DaemonHandle;
use shortcut::register_global_shortcut;
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
                                if let Some(window) = handle.get_webview_window("main") {
                                    let _ = window.show();
                                }
                            }
                            Err(e) => eprintln!("Daemon did not become healthy: {e}"),
                        }
                    }
                    Err(e) => eprintln!("Failed to start daemon: {e}"),
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
        .run(|_app_handle, event| {
            if let RunEvent::Exit = event {
                tauri::async_runtime::block_on(async {
                    // DaemonHandle is managed state; try to stop it cleanly.
                    // We cannot access managed state here easily, so cleanup is done in tray quit.
                });
            }
        });
}
