import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { Mail, Phone, MapPin, Twitter, Linkedin, Instagram, Globe } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { DEFAULT_PLATFORM_ADDRESS_AR } from '../../constants/platformContact';
const LOGO_WHITE = '/nassaq-logo-white.png';
const BG_PATTERN = '/nassaq-background.png';

const MAPS_URL =
  'https://www.google.com/maps/search/?api=1&query=' +
  encodeURIComponent('الهفوف، الاحساء، المملكة العربية السعودية');

const DEFAULT_EMAIL   = 'info@nassaqapp.com';
const DEFAULT_PHONE   = '+966 11 234 5678';
const DEFAULT_WEBSITE = 'nassaqapp.com';

const contactLinkClass =
  'hover:text-brand-turquoise transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise/60 rounded-sm';

export const Footer = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { api } = useAuth();
  const [contactInfo, setContactInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchContactInfo = async () => {
      try {
        const response = await api.get('/public/contact-info');
        setContactInfo(response.data);
      } catch (error) {
        setContactInfo({
          primary_email: DEFAULT_EMAIL,
          support_email: 'support@nassaqapp.com',
          primary_phone: DEFAULT_PHONE,
          address: DEFAULT_PLATFORM_ADDRESS_AR,
          website: DEFAULT_WEBSITE,
          social_media: {}
        });
      } finally {
        setLoading(false);
      }
    };

    fetchContactInfo();
  }, []);

  const email   = contactInfo?.primary_email || DEFAULT_EMAIL;
  const phone   = contactInfo?.primary_phone || DEFAULT_PHONE;
  const address = contactInfo?.address       || DEFAULT_PLATFORM_ADDRESS_AR;
  const website = contactInfo?.website       || DEFAULT_WEBSITE;
  const websiteHref = website.startsWith('http') ? website : `https://${website}`;
  const websiteLabel = website.replace(/^https?:\/\//, '');
  const telHref = `tel:${phone.replace(/\s/g, '')}`;

  // Custom TikTok icon component
  const TikTokIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5" aria-hidden="true">
      <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5 20.1a6.34 6.34 0 0 0 10.86-4.43v-7a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1-.1z"/>
    </svg>
  );

  // Custom Snapchat icon component
  const SnapchatIcon = () => (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5" aria-hidden="true">
      <path d="M12.206.793c.99 0 4.347.276 5.93 3.821.529 1.193.403 3.219.299 4.847l-.003.06c-.012.18-.022.345-.03.51.075.045.203.09.401.09.3-.016.659-.12 1.033-.301a.603.603 0 0 1 .298-.053c.2 0 .4.059.549.153.26.16.398.42.413.673.008.18-.042.36-.152.51-.18.24-.48.39-.93.51-.15.04-.31.08-.46.11-.12.03-.21.05-.287.075-.18.06-.36.18-.39.36-.01.06 0 .12.03.18.21.36.51.84.899 1.32.73.89 1.53 1.59 2.38 2.1.3.18.57.27.81.33.15.03.24.06.27.06a.633.633 0 0 1 .55.63c-.09.42-.45.66-1.2.78-.45.06-.9.15-1.38.27-.21.06-.33.09-.45.15-.15.09-.27.21-.3.36 0 .03 0 .06-.01.09a1.5 1.5 0 0 0 .12.51c.04.06.04.12.04.18a.61.61 0 0 1-.27.51c-.24.15-.54.24-.87.33l-.21.06c-.3.09-.57.21-.87.33-.09.03-.15.06-.21.09-.45.21-.87.51-.87 1.05 0 .09 0 .21.03.33.03.09.06.15.06.21.03.21-.03.45-.21.6-.27.21-.6.33-.96.33-.21 0-.42-.03-.63-.09-.45-.12-.93-.33-1.35-.51-.15-.06-.27-.12-.39-.15-.45-.18-.87-.27-1.32-.27-.6 0-1.2.15-1.8.45-.27.12-.54.27-.84.45-.33.18-.63.33-.93.45-.39.15-.78.24-1.14.24-.15 0-.27 0-.39-.03a.88.88 0 0 1-.27-.09.603.603 0 0 1-.3-.51c0-.06.02-.12.05-.18.04-.09.07-.18.1-.27.04-.18.06-.36.06-.51 0-.06 0-.09-.01-.12-.03-.15-.15-.27-.3-.36-.12-.06-.24-.09-.45-.15-.48-.12-.93-.21-1.38-.27-.75-.12-1.11-.36-1.2-.78a.633.633 0 0 1 .55-.63c.03 0 .12-.03.27-.06.24-.06.51-.15.81-.33.85-.51 1.65-1.21 2.38-2.1.39-.48.69-.96.899-1.32.03-.06.04-.12.03-.18-.03-.18-.21-.3-.39-.36-.077-.025-.167-.045-.287-.075-.15-.03-.31-.07-.46-.11-.45-.12-.75-.27-.93-.51a.633.633 0 0 1-.152-.51c.015-.253.153-.513.413-.673a.752.752 0 0 1 .549-.153c.101 0 .2.018.298.053.374.181.733.285 1.033.301.198 0 .326-.045.401-.09-.008-.165-.018-.33-.03-.51l-.003-.06c-.104-1.628-.23-3.654.299-4.847 1.583-3.545 4.94-3.821 5.93-3.821z"/>
    </svg>
  );

  return (
    <footer data-testid="footer" className="bg-brand-navy text-white relative overflow-hidden">
      <div className="absolute inset-0 opacity-[0.04]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center bottom' }} />
      <div className="absolute inset-0 bg-gradient-to-t from-brand-navy/60 via-transparent to-brand-navy/30" />
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 lg:gap-12">
          {/* Brand Column */}
          <div>
            <Link to="/" className="inline-block mb-6">
              <img src={LOGO_WHITE} alt="نَسَّق" className="h-12 w-auto rounded-xl" />
            </Link>
            <p className="text-white/70 text-sm leading-relaxed font-tajawal mb-6">
              {t('aipoweredIntegratedSchoolManagementPlatformDeliver')}
            </p>
            <div className="flex gap-3 flex-wrap">
              {/* X (Twitter) */}
              <a
                href="https://x.com/nassaqapp"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center hover:bg-brand-turquoise transition-colors"
                aria-label="X (Twitter)"
                data-testid="social-twitter"
              >
                <Twitter className="h-5 w-5" aria-hidden="true" />
              </a>

              {/* Instagram */}
              <a
                href="https://www.instagram.com/nassaqapp/"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center hover:bg-brand-turquoise transition-colors"
                aria-label="Instagram"
                data-testid="social-instagram"
              >
                <Instagram className="h-5 w-5" aria-hidden="true" />
              </a>

              {/* LinkedIn */}
              <a
                href="https://www.linkedin.com/company/nassaqapp"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center hover:bg-brand-turquoise transition-colors"
                aria-label="LinkedIn"
                data-testid="social-linkedin"
              >
                <Linkedin className="h-5 w-5" aria-hidden="true" />
              </a>

              {/* TikTok */}
              <a
                href="https://www.tiktok.com/@nassaqapp"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center hover:bg-brand-turquoise transition-colors"
                aria-label="TikTok"
                data-testid="social-tiktok"
              >
                <TikTokIcon />
              </a>

              {/* Snapchat */}
              <a
                href="https://www.snapchat.com/add/nassaqapp?share_id=2ADaRX5hyPY&locale=en-US"
                target="_blank"
                rel="noopener noreferrer"
                className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center hover:bg-brand-turquoise transition-colors"
                aria-label="Snapchat"
                data-testid="social-snapchat"
              >
                <SnapchatIcon />
              </a>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="font-cairo font-semibold text-lg mb-4">
              {t('quickLinks')}
            </h4>
            <ul className="space-y-3">
              <li>
                <Link
                  to="/login"
                  className="text-white/70 hover:text-brand-turquoise transition-colors text-sm font-tajawal"
                >
                  {t('login')}
                </Link>
              </li>
              <li>
                <Link
                  to="/register"
                  className="text-white/70 hover:text-brand-turquoise transition-colors text-sm font-tajawal"
                >
                  {t('register')}
                </Link>
              </li>
              <li>
                <Link
                  to="/privacy"
                  className="text-white/70 hover:text-brand-turquoise transition-colors text-sm font-tajawal"
                >
                  {t('privacyPolicy')}
                </Link>
              </li>
              <li>
                <Link
                  to="/terms"
                  className="text-white/70 hover:text-brand-turquoise transition-colors text-sm font-tajawal"
                >
                  {t('termsOfService')}
                </Link>
              </li>
            </ul>
          </div>

          {/* Contact Info */}
          <div>
            <h4 className="font-cairo font-semibold text-lg mb-4">
              {t('contactUs')}
            </h4>
            <ul className="space-y-4">
              {/* Email */}
              <li className="flex items-center gap-3 text-white/70 text-sm font-tajawal">
                <Mail className="h-5 w-5 text-brand-turquoise flex-shrink-0" aria-hidden="true" />
                <a
                  href={`mailto:${email}`}
                  className={contactLinkClass}
                  data-testid="footer-email"
                >
                  {email}
                </a>
              </li>

              {/* Phone */}
              <li className="flex items-center gap-3 text-white/70 text-sm font-tajawal">
                <Phone className="h-5 w-5 text-brand-turquoise flex-shrink-0" aria-hidden="true" />
                <a
                  href={telHref}
                  dir="ltr"
                  className={contactLinkClass}
                  data-testid="footer-phone"
                >
                  {phone}
                </a>
              </li>

              {/* Address — opens Google Maps */}
              <li className="flex items-start gap-3 text-white/70 text-sm font-tajawal">
                <MapPin className="h-5 w-5 text-brand-turquoise flex-shrink-0 mt-0.5" aria-hidden="true" />
                <a
                  href={MAPS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={contactLinkClass}
                  data-testid="footer-address"
                >
                  {address}
                </a>
              </li>

              {/* Website */}
              <li className="flex items-center gap-3 text-white/70 text-sm font-tajawal">
                <Globe className="h-5 w-5 text-brand-turquoise flex-shrink-0" aria-hidden="true" />
                <a
                  href={websiteHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={contactLinkClass}
                  data-testid="footer-website"
                >
                  {websiteLabel}
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 pt-8 border-t border-white/10 text-center">
          <p className="text-white/70 text-sm font-tajawal mb-2" data-testid="footer-owner">
            NASSAQ 2026 @
          </p>
          <p className="text-white/50 text-xs font-tajawal tracking-wider">
            Future Element — UVAII VS — IMPACTIA
          </p>
        </div>
      </div>
    </footer>
  );
};
