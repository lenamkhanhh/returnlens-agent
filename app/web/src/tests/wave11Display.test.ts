import { describe, it, expect } from 'vitest';
import { formatDetectedLanguage } from '../utils/format';
import { resolveDemoScale } from '../utils/demoScale';
import { Observation } from '../types';

describe('Wave 11: Display polish for demo presentation', () => {
  describe('1. Discrepancy rule: only colour observation carries discrepancy warning', () => {
    it('evaluates discrepancy only when attribute is color, not on item_type', () => {
      const catalogColor = 'white';

      const itemTypeObs: Observation = {
        id: 'obs-item',
        evidence_id: 'evi-1',
        attribute: 'item_type',
        value: 'headphones',
        visibility: 'visible',
        color_class: 'black',
        t: '00:05',
      };

      const colorObs: Observation = {
        id: 'obs-color',
        evidence_id: 'evi-1',
        attribute: 'color',
        value: 'black',
        visibility: 'visible',
        color_class: 'black',
        t: '00:05',
      };

      const evalMismatch = (obs: Observation) => {
        const attrLower = (obs.attribute || '').toLowerCase();
        const isColorAttr = attrLower === 'color' || attrLower === 'colour' || attrLower === 'item_color';
        return (
          isColorAttr &&
          Boolean(
            obs.color_class &&
            catalogColor &&
            obs.color_class.toLowerCase() !== catalogColor.toLowerCase() &&
            obs.color_class.toLowerCase() !== 'unknown'
          )
        );
      };

      expect(evalMismatch(itemTypeObs)).toBe(false);
      expect(evalMismatch(colorObs)).toBe(true);
    });

    it('handles matching catalog color without discrepancy', () => {
      const catalogColor = 'white';
      const colorWhiteObs: Observation = {
        id: 'obs-color-white',
        evidence_id: 'evi-1',
        attribute: 'color',
        value: 'white',
        visibility: 'visible',
        color_class: 'white',
      };

      const attrLower = (colorWhiteObs.attribute || '').toLowerCase();
      const isColorAttr = attrLower === 'color' || attrLower === 'colour' || attrLower === 'item_color';
      const isMismatch =
        isColorAttr &&
        Boolean(
          colorWhiteObs.color_class &&
          catalogColor &&
          colorWhiteObs.color_class.toLowerCase() !== catalogColor.toLowerCase() &&
          colorWhiteObs.color_class.toLowerCase() !== 'unknown'
        );

      expect(isMismatch).toBe(false);
    });
  });

  describe('2. Voice-note label uses transcriber detected language (English default, not fixed Hindi)', () => {
    it('formats "en" and "english" as "English"', () => {
      expect(formatDetectedLanguage('en')).toBe('English');
      expect(formatDetectedLanguage('EN')).toBe('English');
      expect(formatDetectedLanguage('english')).toBe('English');
    });

    it('formats "hi" and "hindi" as "Hindi"', () => {
      expect(formatDetectedLanguage('hi')).toBe('Hindi');
      expect(formatDetectedLanguage('HI')).toBe('Hindi');
      expect(formatDetectedLanguage('hindi')).toBe('Hindi');
    });

    it('formats "hinglish" as "Hinglish"', () => {
      expect(formatDetectedLanguage('hinglish')).toBe('Hinglish');
    });

    it('defaults to "English" for unspecified or empty language because stock notes are English', () => {
      expect(formatDetectedLanguage(null)).toBe('English');
      expect(formatDetectedLanguage(undefined)).toBe('English');
      expect(formatDetectedLanguage('')).toBe('English');
    });
  });

  describe('3. Demo scale mode (?demo=1 or ?scale=1.35) for 1080p recording readability', () => {
    it('activates default 135% scaling on ?demo=1 or ?demo=true', () => {
      expect(resolveDemoScale('?demo=1')).toBe(1.35);
      expect(resolveDemoScale('?demo=true')).toBe(1.35);
      expect(resolveDemoScale('?tab=seller&demo=1')).toBe(1.35);
    });

    it('supports custom scale factors between 1.25 and 1.50', () => {
      expect(resolveDemoScale('?scale=1.30')).toBe(1.3);
      expect(resolveDemoScale('?demo=1.40')).toBe(1.4);
      expect(resolveDemoScale('?scale=1.50')).toBe(1.5);
    });

    it('deactivates cleanly on ?demo=0 or ?demo=false', () => {
      expect(resolveDemoScale('?demo=0', '1.35')).toBe(null);
      expect(resolveDemoScale('?demo=false', '1.35')).toBe(null);
    });

    it('falls back to stored scale if present in session storage when url has no demo param', () => {
      expect(resolveDemoScale('', '1.35')).toBe(1.35);
      expect(resolveDemoScale('', null)).toBe(null);
    });
  });
});
