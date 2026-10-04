use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Manager};
use tauri_plugin_notification::NotificationExt;

use crate::daemon::DaemonHandle;

pub fn build_tray(handle: &AppHandle) -> Result<(), String> {
    let show_i = MenuItem::with_id(handle, "show", "Show EV", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let hide_i = MenuItem::with_id(handle, "hide", "Hide EV", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let start_i = MenuItem::with_id(handle, "start", "Start daemon", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let stop_i = MenuItem::with_id(handle, "stop", "Stop daemon", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let updates_i = MenuItem::with_id(handle, "updates", "Check for updates", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let settings_i = MenuItem::with_id(handle, "settings", "Settings", true, None::<&str>)
        .map_err(|e| e.to_string())?;
    let quit_i = MenuItem::with_id(handle, "quit", "Quit", true, None::<&str>)
        .map_err(|e| e.to_string())?;

    let sep1 = PredefinedMenuItem::separator(handle).map_err(|e| e.to_string())?;
    let sep2 = PredefinedMenuItem::separator(handle).map_err(|e| e.to_string())?;

    let menu = Menu::with_items(
        handle,
        &[
            &show_i,
            &hide_i,
            &sep1,
            &start_i,
            &stop_i,
            &updates_i,
            &settings_i,
            &sep2,
            &quit_i,
        ],
    )
    .map_err(|e| format!("Failed to build tray menu: {e}"))?;

    let default_icon = handle
        .default_window_icon()
        .cloned()
        .ok_or("No default window icon available")?;

    let _ = TrayIconBuilder::new()
        .icon(default_icon)
        .menu(&menu)
        .on_menu_event(|handle, event| {
            let handle = handle.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = handle_tray_event(&handle, event.id.as_ref()).await {
                    eprintln!("Tray event error: {e}");
                }
            });
        })
        .build(handle)
        .map_err(|e| format!("Failed to create tray icon: {e}"))?;

    Ok(())
}

async fn handle_tray_event(handle: &AppHandle, id: &str) -> Result<(), String> {
    match id {
        "show" => {
            if let Some(window) = handle.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
        "hide" => {
            if let Some(window) = handle.get_webview_window("main") {
                let _ = window.hide();
            }
        }
        "settings" => {
            if let Some(window) = handle.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
                let _ = window.eval("window.location.href = '/setup'");
            }
        }
        "start" => {
            let state = handle.state::<DaemonHandle>();
            let daemon = state.inner().clone();
            // Default to system python and project root; in production these come from env/config.
            let python_bin = std::env::var("EV_PYTHON_BIN").unwrap_or_else(|_| "python".to_string());
            let working_dir = std::env::var("EV_WORKING_DIR").unwrap_or_else(|_| ".".to_string());
            daemon.start(python_bin, working_dir).await?;
            daemon.wait_for_health(30).await?;
        }
        "stop" => {
            let state = handle.state::<DaemonHandle>();
            state.stop().await?;
        }
        "updates" => {
            let state = handle.state::<DaemonHandle>();
            let url = format!("{}/update/check", state.base_url);
            match reqwest::get(&url).await {
                Ok(resp) if resp.status().is_success() => {
                    let info: serde_json::Value = resp.json().await.unwrap_or_default();
                    let (title, body) = match info.get("update_available").and_then(|v| v.as_bool()) {
                        Some(true) => {
                            let latest = info.get("latest").and_then(|v| v.as_str()).unwrap_or("newer");
                            let url = info.get("url").and_then(|v| v.as_str()).unwrap_or("https://github.com/satyamdas03/Hi-EV/releases");
                            (
                                "Hi-EV update available",
                                format!("Version {latest} is available. Installer: {url}"),
                            )
                        }
                        _ => (
                            "Hi-EV is up to date",
                            format!(
                                "Current version: {}",
                                info.get("current").and_then(|v| v.as_str()).unwrap_or("unknown")
                            ),
                        ),
                    };
                    let _ = handle.notification().builder().title(title).body(body).show();
                }
                _ => {
                    let _ = handle
                        .notification()
                        .builder()
                        .title("Hi-EV update check failed")
                        .body("Could not reach the Hi-EV daemon to check for updates.")
                        .show();
                }
            }
        }
        "quit" => {
            let state = handle.state::<DaemonHandle>();
            let _ = state.stop().await;
            handle.exit(0);
        }
        _ => {}
    }
    Ok(())
}
