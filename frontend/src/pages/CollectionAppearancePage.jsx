import { useState } from 'react';
import { useParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextInput, Button } from 'hds-react';
import PageLayout from '../components/PageLayout';
import ImageUpload from '../components/ImageUpload';
import TheeemeSelector from '../components/TheeemeSelector';
import KoroSelector from '../components/KoroSelector';
import TagInput from '../components/TagInput';
import FieldNotice from '../components/FieldNotice';
import LoadingSpinner from '../components/LoadingSpinner';
import CollectionFormRefusal from '../components/CollectionFormRefusal';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import useTheeemeList from '../hooks/useTheeemeList';
import useCollectionForm from '../hooks/useCollectionForm';
import useDocumentTitle from '../hooks/useDocumentTitle';
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
  const { btnStyle } = useTheeeme();
  const theeemes = useTheeemeList();
  const [headline, setHeadline] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  const [theeeme, setTheeeme] = useState('');
  const [koro, setKoro] = useState('basic');
  const [tags, setTags] = useState([]);
  const [homePage, setHomePage] = useState('');
  const { loading, loaded, refusal, base, save, submitting, toast, setToast } = useCollectionForm(
    code,
    {
      onLoad: (data) => {
        setHeadline(data.headline || '');
        setThumbnail(data.thumbnail || '');
        setThumbnailUrl(data.thumbnail_url || '');
        setTheeeme(data.theeeme || '');
        setKoro(data.koro || 'basic');
        setTags(data.tags || []);
        setHomePage(data.home_page || '');
      },
    }
  );
  useDocumentTitle(
    headline
      ? t('titles.collectionAppearance', { headline: L(headline) })
      : t('titles.collectionAppearanceDefault')
  );

  const handleSubmit = () => {
    if (!loaded) return;
    const body = {
      thumbnail: thumbnail || '',
      koro,
      tags,
      home_page: homePage.trim(),
    };
    if (theeeme) body.theeeme = theeeme;
    save(body);
  };

  if (loading) return <LoadingSpinner />;
  if (refusal) return <CollectionFormRefusal refusal={refusal} base={base} />;

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
