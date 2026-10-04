use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};
use keyboard_types::{Code, Modifiers};

use crate::daemon::DaemonHandle;

pub fn register_global_shortcut(handle: &AppHandle) -> Result<(), String> {
    let shortcut = parse_shortcut()?;
    let app_handle = handle.clone();

    handle
        .global_shortcut()
        .on_shortcut(shortcut, move |_, _, event| {
            if event.state == ShortcutState::Released {
                return;
            }
            let app_handle = app_handle.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = on_shortcut(&app_handle).await {
                    eprintln!("Global shortcut error: {e}");
                }
            });
        })
        .map_err(|e| format!("Failed to register global shortcut {shortcut}: {e}"))?;

    Ok(())
}

async fn on_shortcut(handle: &AppHandle) -> Result<(), String> {
    let daemon = handle.state::<DaemonHandle>().inner().clone();

    // Ensure the daemon is running.
    if !daemon.is_running().await {
        let python_bin = std::env::var("EV_PYTHON_BIN").unwrap_or_else(|_| "python".to_string());
        let working_dir = std::env::var("EV_WORKING_DIR").unwrap_or_else(|_| ".".to_string());
        daemon.start(python_bin, working_dir).await?;
        daemon.wait_for_health(30).await?;
    }

    // Bring window to foreground.
    if let Some(window) = handle.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }

    // Notify the frontend to start a voice turn.
    if let Some(window) = handle.get_webview_window("main") {
        let _ = window.emit("ev:shortcut-triggered", ());
    }

    Ok(())
}

fn parse_shortcut() -> Result<Shortcut, String> {
    #[cfg(target_os = "macos")]
    let modifiers = Modifiers::META | Modifiers::SHIFT;
    #[cfg(not(target_os = "macos"))]
    let modifiers = Modifiers::CONTROL | Modifiers::ALT;

    let code = Code::KeyE;
    Ok(Shortcut::new(Some(modifiers), code))
}

pub fn shortcut_string() -> String {
    #[cfg(target_os = "macos")]
    return "Cmd+Shift+E".to_string();
    #[cfg(not(target_os = "macos"))]
    return "Ctrl+Alt+E".to_string();
}
