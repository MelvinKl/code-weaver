/**
 * Project-level pi-jev configuration (https://pi.dev/packages/pi-jev).
 *
 * Project extensions load before package extensions, so the environment
 * variables set here are already in place when the pi-jev package extension
 * reads them at load time:
 *
 *  - PI_JEV_BASE_URL points the TypeSafe Jev client at Laya (laya-serve)
 *    served behind llama-swap on 192.168.5.2:8011. Custom endpoints omit
 *    the API key, so no TYPESAFE_API_KEY is needed.
 *  - PI_JEV_COMPACT=1 enables Jev-assisted /compact by default
 *    (pi-jev's --jev-compact flag defaults to this env var).
 *  - PI_JEV_THINKING=1 enables per-prompt reasoning-level control by
 *    default (pi-jev's --jev-thinking flag defaults to this env var).
 *  - PI_JEV_AGENTS=1 enables Jev-driven agent selection for the
 *    pi-subagents package by default.
 *
 * Values already present in the environment (e.g. set per machine in
 * ~/.bashrc) are left untouched.
 */

const JEV_ENV: Record<string, string> = {
  PI_JEV_BASE_URL: "http://192.168.5.2:8011",
  PI_JEV_COMPACT: "1",
  PI_JEV_THINKING: "1",
  PI_JEV_AGENTS: "1",
};

export default function () {
  for (const [name, value] of Object.entries(JEV_ENV)) {
    if (!process.env[name]) {
      process.env[name] = value;
    }
  }
}
