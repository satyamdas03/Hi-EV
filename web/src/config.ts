/**
 * Runtime configuration for the Hi-EV web face.
 *
 * All values can be overridden at build time via VITE_* env variables.
 * The defaults point at the local Hi-EV daemon.
 */

export const EV_WS_URL = import.meta.env.VITE_EV_WS_URL ?? 'ws://127.0.0.1:7345/ws'
export const EV_API_URL = import.meta.env.VITE_EV_API_URL ?? 'http://127.0.0.1:7345'
