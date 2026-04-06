export const FEATURE_FLAGS = {
  refactorBundleDNavigation: import.meta.env.VITE_ENABLE_REFACTOR_BUNDLE_D_NAVIGATION !== '0',
} as const;
