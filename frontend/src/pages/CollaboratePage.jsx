import ContactFormPage from '../components/ContactFormPage';

/**
 * The collaborate door (`/collaborate`): the shared operator-message form with
 * collaboration copy — design, product, code and beta-testing hands from the
 * open-source and social-economy worlds. Same pipe as /contact, `collab` kind
 * (the operator's inbox label differs).
 */
export default function CollaboratePage() {
  return (
    <ContactFormPage
      docTitleKey="titles.collaborate"
      titleKey="collaborate.pageTitle"
      introKey="collaborate.intro"
      kind="collab"
      idPrefix="collaborate"
    />
  );
}
