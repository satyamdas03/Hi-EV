use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};
use keyboard_types::{Code, Modifiers};

use crate::daemon::DaemonHandle;

pub fn register_global_shortcut(handle: &AppHandle) -> Result<(), String> {
    let shortcut = parse_shortcut_env().unwrap_or_else(|e| {
        eprintln!("Invalid EV_GLOBAL_HOTKEY, using default: {e}");
        default_shortcut()
    });
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

fn default_shortcut() -> Shortcut {
    #[cfg(target_os = "macos")]
    let modifiers = Modifiers::META | Modifiers::SHIFT;
    #[cfg(not(target_os = "macos"))]
    let modifiers = Modifiers::CONTROL | Modifiers::ALT;
    Shortcut::new(Some(modifiers), Code::KeyE)
}

fn parse_shortcut_env() -> Result<Shortcut, String> {
    let raw = std::env::var("EV_GLOBAL_HOTKEY").map_err(|_| "not set".to_string())?;
    let tokens: Vec<String> = raw
        .to_lowercase()
        .split('+')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();
    if tokens.is_empty() {
        return Err("empty shortcut".to_string());
    }

    let key_token = tokens.last().cloned().unwrap_or_default();
    let code = parse_key(&key_token)?;

    let mut modifiers = Modifiers::empty();
    for tok in &tokens[..tokens.len() - 1] {
        match tok.as_str() {
            "ctrl" | "control" => modifiers |= Modifiers::CONTROL,
            "alt" | "option" => modifiers |= Modifiers::ALT,
            "shift" => modifiers |= Modifiers::SHIFT,
            "cmd" | "command" | "meta" | "super" | "win" => modifiers |= Modifiers::META,
            _ => return Err(format!("Unknown modifier: {tok}")),
        }
    }

    // Require at least one modifier so the shortcut is not a single key.
    if modifiers.is_empty() {
        return Err("Shortcut must include at least one modifier".to_string());
    }

    Ok(Shortcut::new(Some(modifiers), code))
}

fn parse_key(token: &str) -> Result<Code, String> {
    if token.len() == 1 {
        let ch = token.chars().next().unwrap();
        if ch.is_ascii_alphabetic() {
            // keyboard_types uses KeyA..KeyZ.
            let code_str = format!("Key{}", ch.to_ascii_uppercase());
            return code_str
                .parse()
                .map_err(|_| format!("Unknown letter key: {token}"));
        }
        if ch.is_ascii_digit() {
            let code_str = format!("Digit{ch}");
            return code_str
                .parse()
                .map_err(|_| format!("Unknown digit key: {token}"));
        }
    }

    if let Some(rest) = token.strip_prefix('f') {
        if let Ok(num) = rest.parse::<u8>() {
            if (1..=24).contains(&num) {
                let code_str = format!("F{num}");
                return code_str
                    .parse()
                    .map_err(|_| format!("Unknown function key: {token}"));
            }
        }
    }

    // Try a direct parse for tokens like "space", "enter", etc.
    let capitalized = token
        .chars()
        .enumerate()
        .map(|(i, c)| {
            if i == 0 {
                c.to_ascii_uppercase()
            } else {
                c
            }
        })
        .collect::<String>();
    capitalized
        .parse()
        .map_err(|_| format!("Unsupported key: {token}"))
}

pub fn shortcut_string() -> String {
    match std::env::var("EV_GLOBAL_HOTKEY") {
        Ok(s) if !s.is_empty() => s,
        #[cfg(target_os = "macos")]
        _ => "Cmd+Shift+E".to_string(),
        #[cfg(not(target_os = "macos"))]
        _ => "Ctrl+Alt+E".to_string(),
    }
}
