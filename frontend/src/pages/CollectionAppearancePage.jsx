import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextInput, Button } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import ImageUpload from '../components/ImageUpload';
import TheeemeSelector from '../components/TheeemeSelector';
import KoroSelector from '../components/KoroSelector';
import TagInput from '../components/TagInput';
import FieldNotice from '../components/FieldNotice';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import useTheeemeList from '../hooks/useTheeemeList';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { useLocalized } from '../utils/localized';

const TAGS_EXAMPLE = '{"es": "Juguetes", "ca": "Joguines"}';

/**
 * The collection's look: logo, palette, wave, tags and the page "Home" leads to.
 *
 * It sends only these fields (`thumbnail`, `koro`, `tags`, `home_page`, and
 * `theeeme` when one is chosen) and only once the collection has loaded: the
 * PATCH is partial, so nothing else of the collection is touched, and the save
 * button stays disabled while it loads so a save can never carry blanks.
 */
export default function CollectionAppearancePage() {
  const { t } = useTranslation();
  const L = useLocalized();
  const { code } = useParams();
  const base = useCollectionBase(code);
  const navigate = useNavigate();
  const { btnStyle } = useTheeeme();
  const theeemes = useTheeemeList();
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [headline, setHeadline] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  const [theeeme, setTheeeme] = useState('');
  const [koro, setKoro] = useState('basic');
  const [tags, setTags] = useState([]);
  const [homePage, setHomePage] = useState('');
  // The page wears the palette the collection has saved, not the one being tried.
  const [savedPalette, setSavedPalette] = useState(null);
  useCollectionTheeeme(savedPalette?.colors, savedPalette?.koro);
  const [savedLanguage, setSavedLanguage] = useState('');
  const [savedTexts, setSavedTexts] = useState([]);
  useCollectionLanguage(savedLanguage, savedTexts);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  useDocumentTitle(
    headline
      ? t('titles.collectionAppearance', { headline: L(headline) })
      : t('titles.collectionAppearanceDefault')
  );

  useEffect(() => {
    const load = async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`);
        if (res.ok) {
          const data = await res.json();
          setHeadline(data.headline || '');
          setThumbnail(data.thumbnail || '');
          setThumbnailUrl(data.thumbnail_url || '');
          setTheeeme(data.theeeme || '');
          setKoro(data.koro || 'basic');
          setTags(data.tags || []);
          setHomePage(data.home_page || '');
          setSavedPalette({ colors: data.theeeme_colors, koro: data.koro });
          setSavedLanguage(data.language || '');
          setSavedTexts([data.headline, data.description]);
          setLoaded(true);
        } else {
          setToast({ type: 'error', messageKey: 'editCollection.errorLoading' });
        }
      } catch {
        setToast({ type: 'error', messageKey: 'common.connectionError' });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [code]);

  const handleSubmit = async () => {
    if (!loaded) return;
    setSubmitting(true);
    setToast(null);
    const body = {
      thumbnail: thumbnail || '',
      koro,
      tags,
      home_page: homePage.trim(),
    };
    if (theeeme) body.theeeme = theeeme;
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(base);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
        const message = await extractApiError(res);
        setToast({ type: 'error', message: message || t('editCollection.errorSaving') });
      } else {
        setToast({ type: 'error', message: t('editCollection.errorSaving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <PageLayout backTo={base} backLabel={L(headline) || t('common.collection')}>
      <h1 className="page-title-xl">{t('collectionSettings.appearance')}</h1>
      <div className="form-grid">
        <ImageUpload
          id="appearance-thumbnail"
          label={t('collectionSettings.logoLabel')}
          helperText={t('collectionSettings.logoHelper')}
          onChange={setThumbnail}
          currentUrl={thumbnailUrl}
          folder="oiueei/collections"
        />
        <TheeemeSelector theeemes={theeemes} value={theeeme} onChange={setTheeeme} />
        <KoroSelector value={koro} onChange={setKoro} />
        <div>
          <FieldNotice
            id="appearance-tags-notice"
            label={t('createCollection.tagsLabel')}
            example={TAGS_EXAMPLE}
          >
            {t('localized.tagsNotice')}
          </FieldNotice>
          <TagInput
            tags={tags}
            onChange={setTags}
            label={t('createCollection.tagsLabel')}
            placeholder={t('createCollection.tagsPlaceholder')}
            helperText={t('createCollection.tagsHelper')}
          />
        </div>
        <TextInput
          id="appearance-home-page"
          type="url"
          label={t('homePage.label')}
          helperText={t('homePage.helper')}
          placeholder="https://…"
          value={homePage}
          onChange={(e) => setHomePage(e.target.value)}
          maxLength={128}
        />
      </div>
      <div className="form-actions">
        <Button
          disabled={submitting || !loaded}
          onClick={handleSubmit}
          style={{ ...btnStyle, width: '100%' }}
        >
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
