import { useParams } from 'react-router-dom';
import MagicLinkJoinPage from '../components/MagicLinkJoinPage';

export default function SharePage() {
  const { token } = useParams();
  return (
    <MagicLinkJoinPage
      ns="share"
      docTitleKey="titles.share"
      titleKey="share.pageTitle"
      descriptionKey="share.pageDescription"
      extraBody={{ share_token: token }}
    />
  );
}
