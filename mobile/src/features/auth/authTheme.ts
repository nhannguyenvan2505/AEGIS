export const authThemes = {
  login: {
    background: '#f7f3e8',
    text: '#12332b',
    muted: '#566a63',
    placeholder: '#7b8e87',
    border: '#d9d2bf',
    primary: '#0b7a54',
    link: '#0b7a54',
    iconBackground: '#0b7a54',
    icon: '#ffffff',
  },
  register: {
    background: '#f7f3e8',
    text: '#12332b',
    muted: '#566a63',
    placeholder: '#7b8e87',
    border: '#d9d2bf',
    primary: '#0b7a54',
    link: '#0b7a54',
    iconBackground: '#d3f1e2',
    icon: '#0b7a54',
  },
} as const;

export type AuthVariant = keyof typeof authThemes;
