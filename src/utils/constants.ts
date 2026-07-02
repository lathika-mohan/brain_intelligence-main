export const PLATFORM_ROLES = {
  SUPER_ADMIN: 'SUPER_ADMIN',
  PLANT_MANAGER: 'PLANT_MANAGER',
  CONTROL_ROOM_OPERATOR: 'CONTROL_ROOM_OPERATOR',
  MAINTENANCE_ENGINEER: 'MAINTENANCE_ENGINEER',
} as const;

export const BREAKPOINTS = {
  SM: 600,
  MD: 900,
  LG: 1200,
  XL: 1536,
} as const;

export const STORAGE_KEYS = {
  AUTH_TOKEN: 'iob_auth_token',
  SIDEBAR_STATE: 'iob_sidebar_open',
  THEME_MODE: 'iob_theme_mode',
} as const;

export const AUTH_TOKEN_KEY = STORAGE_KEYS.AUTH_TOKEN;
