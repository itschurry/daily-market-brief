const STORAGE_KEYS = {
  draftQuery: 'wp_config_draft_query_v1',
  draftSettings: 'wp_config_draft_settings_v1',
  validationTransfer: 'wp_lab_validation_transfer_v2',
} as const;

const LEGACY_STORAGE_KEYS = {
  draftQuery: 'backtest_query_v3',
  draftSettings: 'console_validation_settings_draft_v1',
  validationTransfer: 'console_strategy_validation_transfer_v1',
} as const;

export const CONFIG_DRAFT_QUERY_STORAGE_KEY = STORAGE_KEYS.draftQuery;
export const CONFIG_DRAFT_SETTINGS_STORAGE_KEY = STORAGE_KEYS.draftSettings;
export const VALIDATION_TRANSFER_STORAGE_KEY = STORAGE_KEYS.validationTransfer;

export interface StorageMigrationReport {
  migratedKeys: string[];
  removedKeys: string[];
}

function copyIfPresent(fromKey: string, toKey: string, report: StorageMigrationReport) {
  const raw = localStorage.getItem(fromKey);
  if (!raw || localStorage.getItem(toKey)) return;
  localStorage.setItem(toKey, raw);
  report.migratedKeys.push(`${fromKey} -> ${toKey}`);
}

function removeIfPresent(key: string, report: StorageMigrationReport) {
  if (localStorage.getItem(key) === null) return;
  localStorage.removeItem(key);
  report.removedKeys.push(key);
}

export function migrateLegacyConsoleStorage(): StorageMigrationReport {
  if (typeof window === 'undefined') {
    return { migratedKeys: [], removedKeys: [] };
  }

  const report: StorageMigrationReport = { migratedKeys: [], removedKeys: [] };
  copyIfPresent(LEGACY_STORAGE_KEYS.draftQuery, STORAGE_KEYS.draftQuery, report);
  copyIfPresent(LEGACY_STORAGE_KEYS.draftSettings, STORAGE_KEYS.draftSettings, report);
  copyIfPresent(LEGACY_STORAGE_KEYS.validationTransfer, STORAGE_KEYS.validationTransfer, report);

  removeIfPresent(LEGACY_STORAGE_KEYS.draftQuery, report);
  removeIfPresent(LEGACY_STORAGE_KEYS.draftSettings, report);
  removeIfPresent(LEGACY_STORAGE_KEYS.validationTransfer, report);

  return report;
}

export function loadStoredJson<T>(key: string): T | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function saveStoredJson(key: string, value: unknown) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(key, JSON.stringify(value));
}
