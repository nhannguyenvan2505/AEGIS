import { useState, type Ref } from 'react';
import { Pressable, Text, TextInput, View, type TextInputProps } from 'react-native';
import { Icon, type IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { authThemes, type AuthVariant } from '../authTheme';

type AuthFieldProps = Omit<TextInputProps, 'style' | 'secureTextEntry'> & {
  label: string;
  icon: IconName;
  password?: boolean;
  error?: string;
  hint?: string;
  variant?: AuthVariant;
  ref?: Ref<TextInput>;
};

export function AuthField({ label, icon, password = false, error, hint, variant, ref, ...inputProps }: AuthFieldProps) {
  const [visible, setVisible] = useState(false);
  const [focused, setFocused] = useState(false);
  const theme = variant ? authThemes[variant] : undefined;
  const iconColor = error ? '#be123c' : theme?.placeholder ?? '#64748b';

  return (
    <View style={s.authField}>
      <Text style={[s.authFieldLabel, theme && s.authPageFieldLabel, theme && { color: theme.text }]}>{label}</Text>
      <View style={[
        s.authInputRow,
        theme && s.authPageInputRow,
        theme && { borderColor: theme.border },
        focused && { borderColor: theme?.primary ?? '#059669' },
        !!error && s.authInputInvalid,
      ]}>
        {!theme && <Icon name={icon} size={19} color={iconColor} />}
        <TextInput
          ref={ref}
          accessibilityLabel={label}
          accessibilityHint={error || hint}
          placeholderTextColor={theme?.placeholder ?? '#94a3b8'}
          selectionColor={theme?.primary ?? '#059669'}
          underlineColorAndroid="transparent"
          autoCapitalize={inputProps.autoCapitalize ?? 'none'}
          autoCorrect={inputProps.autoCorrect ?? false}
          autoComplete={password ? 'off' : undefined}
          importantForAutofill={password ? 'no' : 'auto'}
          {...inputProps}
          style={[s.authInput, theme && s.authPageInput, theme && { color: theme.text }]}
          secureTextEntry={password && !visible}
          onFocus={event => { setFocused(true); inputProps.onFocus?.(event); }}
          onBlur={event => { setFocused(false); if (password) setVisible(false); inputProps.onBlur?.(event); }}
        />
        {!!theme && !password && (
          <View style={s.authPageFieldIcon}><Icon name={icon} size={20} color={iconColor} /></View>
        )}
        {password && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${visible ? 'Ẩn' : 'Hiển thị'} ${label.toLowerCase()}`}
            accessibilityState={{ selected: visible }}
            style={s.authVisibility}
            onPress={() => setVisible(current => !current)}
          >
            <Icon name={theme ? (visible ? 'eye' : 'eye-off') : (visible ? 'eye-off' : 'eye')} size={20} color={iconColor} />
          </Pressable>
        )}
      </View>
      {!!error && <Text accessibilityLiveRegion="polite" style={s.authFieldError}>{error}</Text>}
      {!error && !!hint && <Text style={[s.authHint, theme && s.authPageHint, theme && { color: theme.placeholder }]}>{hint}</Text>}
    </View>
  );
}
