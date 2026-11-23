import { getTheme, dark, light, typography, spacing, radius } from '../theme';

describe('theme', () => {
  describe('getTheme', () => {
    it('returns light palette by default', () => {
      const theme = getTheme();
      expect(theme.isDark).toBe(false);
      expect(theme.bg.surfacePrimary).toBe(light.bg.surfacePrimary);
      expect(theme.text.primary).toBe(light.text.primary);
    });

    it('returns dark palette when isDark is true', () => {
      const theme = getTheme(true);
      expect(theme.isDark).toBe(true);
      expect(theme.bg.surfacePrimary).toBe(dark.bg.surfacePrimary);
      expect(theme.text.primary).toBe(dark.text.primary);
    });

    it('includes typography, spacing and radius', () => {
      const theme = getTheme();
      expect(theme.typography).toBe(typography);
      expect(theme.spacing).toBe(spacing);
      expect(theme.radius).toBe(radius);
    });
  });

  describe('dark palette', () => {
    it('has correct background colors', () => {
      expect(dark.bg.surfacePrimary).toBe('#000000');
      expect(dark.bg.surfaceSecondary).toBe('#141414');
      expect(dark.bg.surfaceTertiary).toBe('#1B1B1B');
      expect(dark.bg.surfaceElevated1).toBe('#141414');
      expect(dark.bg.surfaceElevated2).toBe('#1F1F1F');
      expect(dark.bg.surfaceElevated3).toBe('#242424');
    });

    it('has correct text colors', () => {
      expect(dark.text.primary).toBe('#FFFFFF');
      expect(dark.text.secondary).toBe('#AFAFAF');
      expect(dark.text.tertiary).toBe('#757575');
      expect(dark.text.highlight).toBe('#365DFF');
    });

    it('has correct icon colors', () => {
      expect(dark.icon.primary).toBe('#FFFFFF');
      expect(dark.icon.secondary).toBe('#808080');
      expect(dark.icon.accent).toBe('#8CA2FF');
    });

    it('has correct primary button colors', () => {
      expect(dark.buttonPrimary.bg).toBe('#0434FF');
      expect(dark.buttonPrimary.text).toBe('#FFFFFF');
      expect(dark.buttonPrimary.bgDisabled).toBe('#334155');
    });

    it('has correct status colors', () => {
      expect(dark.status.success).toBe('#00DD00');
      expect(dark.status.warning).toBe('#FF920A');
      expect(dark.status.draft).toBe('#FFE50D');
      expect(dark.status.error).toBe('#FF2C20');
    });

    it('has correct border colors', () => {
      expect(dark.border.divider).toBe('#333333');
      expect(dark.border.subtle).toBe('#1F1F1F');
      expect(dark.border.listDivider).toBe('#383838');
    });

    it('has correct navigation colors', () => {
      expect(dark.topNav.bg).toBe('#000000');
      expect(dark.topNav.text).toBe('#FFFFFF');
      expect(dark.bottomNav.bg).toBe('#1E293B');
    });

    it('has correct input field colors', () => {
      expect(dark.input.bg).toBe('#252525');
      expect(dark.input.border).toBe('#475569');
      expect(dark.input.textInput).toBe('#FFFFFF');
      expect(dark.input.errorBorder).toBe('#FF2C20');
    });
  });

  describe('light palette', () => {
    it('has correct background colors', () => {
      expect(light.bg.surfacePrimary).toBe('#EEEEEE');
      expect(light.bg.surfaceSecondary).toBe('#FFFFFF');
      expect(light.bg.surfaceElevated1).toBe('#FFFFFF');
    });

    it('has correct text colors', () => {
      expect(light.text.primary).toBe('#141414');
      expect(light.text.secondary).toBe('#333333');
      expect(light.text.tertiary).toBe('#545454');
      expect(light.text.highlight).toBe('#0434FF');
    });

    it('has correct status colors', () => {
      expect(light.status.success).toBe('#086C0C');
      expect(light.status.warning).toBe('#A1440B');
      expect(light.status.error).toBe('#C8170D');
    });

    it('has correct primary button colors', () => {
      expect(light.buttonPrimary.bg).toBe('#0434FF');
      expect(light.buttonPrimary.text).toBe('#FFFFFF');
    });
  });

  describe('typography', () => {
    it('uses Inter font family', () => {
      expect(typography.fontFamily).toBe('Inter');
    });

    it('has expected size scale', () => {
      expect(typography.size.xs).toBe(12);
      expect(typography.size.sm).toBe(14);
      expect(typography.size.md).toBe(16);
      expect(typography.size.lg).toBe(18);
      expect(typography.size.xl).toBe(20);
      expect(typography.size.xxl).toBe(24);
    });

    it('has matching line heights', () => {
      expect(typography.lineHeight.xs).toBe(16);
      expect(typography.lineHeight.md).toBe(24);
      expect(typography.lineHeight.xl).toBe(28);
    });

    it('has weight scale', () => {
      expect(typography.weight.light).toBe('300');
      expect(typography.weight.regular).toBe('400');
      expect(typography.weight.medium).toBe('500');
      expect(typography.weight.bold).toBe('700');
    });
  });

  describe('spacing', () => {
    it('follows 4-pt grid', () => {
      expect(spacing.xs).toBe(4);
      expect(spacing.sm).toBe(8);
      expect(spacing.md).toBe(12);
      expect(spacing.lg).toBe(16);
      expect(spacing.xl).toBe(20);
      expect(spacing.xxl).toBe(24);
    });
  });

  describe('radius', () => {
    it('has expected values', () => {
      expect(radius.xs).toBe(4);
      expect(radius.sm).toBe(8);
      expect(radius.md).toBe(12);
      expect(radius.full).toBe(9999);
    });
  });
});
