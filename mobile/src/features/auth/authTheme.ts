export const authThemes = {
  login: {
    background: '#edf2f6',
    text: '#123f43',
    muted: '#526e70',
    placeholder: '#526e70',
    border: '#c8d5d3',
    primary: '#1db69b',
    link: '#123f43',
    iconBackground: '#1db69b',
    icon: '#ffffff',
  },
  register: {
    background: '#e8edf2',
    text: '#1c2748',
    muted: '#4e5d78',
    placeholder: '#6e80a7',
    border: '#cbd6e6',
    primary: '#009b73',
    link: '#009b73',
    iconBackground: '#cefae5',
    icon: '#009b73',
  },
} as const;

export type AuthVariant = keyof typeof authThemes;
