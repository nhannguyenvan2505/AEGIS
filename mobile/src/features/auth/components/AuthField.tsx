import { useState, type Ref } from 'react';
import { Pressable, Text, TextInput, View, type TextInputProps } from 'react-native';
import { Icon, type IconName } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';

type AuthFieldProps = Omit<TextInputProps, 'style' | 'secureTextEntry'> & {
  label: string;
  icon: IconName;
  password?: boolean;
  error?: string;
  hint?: string;
  ref?: Ref<TextInput>;
};

export function AuthField({ label, icon, password = false, error, hint, ref, ...inputProps }: AuthFieldProps) {
  const [visible, setVisible] = useState(false);
  const [focused, setFocused] = useState(false);

  return (
    <View style={s.authField}>
      <Text style={s.authFieldLabel}>{label}</Text>
      <View style={[s.authInputRow, focused && s.authInputFocused, !!error && s.authInputInvalid]}>
        <Icon name={icon} size={19} color={error ? '#be123c' : '#64748b'} />
        <TextInput
          ref={ref}
          accessibilityLabel={label}
          accessibilityHint={error || hint}
          placeholderTextColor="#94a3b8"
          selectionColor="#059669"
          underlineColorAndroid="transparent"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete={password ? 'off' : undefined}
          importantForAutofill={password ? 'no' : 'auto'}
          {...inputProps}
          style={s.authInput}
          secureTextEntry={password && !visible}
          onFocus={event => { setFocused(true); inputProps.onFocus?.(event); }}
          onBlur={event => { setFocused(false); if (password) setVisible(false); inputProps.onBlur?.(event); }}
        />
        {password && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${visible ? 'Ẩn' : 'Hiển thị'} ${label.toLowerCase()}`}
            accessibilityState={{ selected: visible }}
            style={s.authVisibility}
            onPress={() => setVisible(current => !current)}
          >
            <Icon name={visible ? 'eye-off' : 'eye'} size={20} color="#64748b" />
          </Pressable>
        )}
      </View>
      {!!error && <Text accessibilityLiveRegion="polite" style={s.authFieldError}>{error}</Text>}
      {!error && !!hint && <Text style={s.authHint}>{hint}</Text>}
    </View>
  );
}
