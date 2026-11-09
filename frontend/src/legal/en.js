// Instance legal text — generic version shipped with the standalone repo.
// Every OIUEEI deployment has its own operator, and that operator is the data
// controller: if you self-host OIUEEI, edit the "Who operates this instance"
// section with your identity and contact details.
// (A deployment can replace this file with its own text, carrying its owner's
// real details.)
export default `
# Our commitment

OIUEEI runs without ads and without third-party analytics: nobody tracks you while you use it. Your data is not the product — it is never sold or shared with anyone. There are no tracking pixels in the emails and no links wrapped in trackers. This commitment is written into the project's design rules; it's the starting point, not the fine print.

# Who operates this instance

OIUEEI is open source software (EUPL-1.2 licence). This page describes **one instance** of OIUEEI: whoever operates it is responsible for the service and for how your data is handled.

*The operator of this instance has not yet completed this section with their identity and contact details. If you run this deployment, edit \`frontend/src/legal/\` with your details.*

# Privacy

**What the app stores, by design:** your email (to sign in with magic links — no passwords), your name and optional profile (bio, photo, language), the content you publish (collections, things and their photos, questions and answers, requests), your email preferences, and **optional** demographics (birth-year generation and postal code) visible only to the people who run your communities, in aggregate — never public.

**What we count (numbers only):** each day, how many signed-in people used the app from a phone and how many from another device (a computer or a tablet), and how many times a collection or a thing was saved from each. We keep only those numbers — not who, and not your browser's details.

**Where it goes:** email leaves through whatever SMTP provider the operator configured, and images and documents are stored in the operator's own object-storage bucket. Nothing else leaves the instance: no third-party SDKs, no events sent anywhere. Usage metrics are first-party, pseudonymised and never shared.

**Who sees what inside a group:** a request you make for a thing (a loan, a rental, a gift, a purchase or a reservation) reaches whoever runs that thing — its owner and, in a group run by a team, the people who run it — with your name and your email, so they can answer you. If the group asks for it when you book, you can also leave a contact phone number: it is optional, only those who manage that booking see it, and it is deleted the day after the booking. A question you ask on a thing is shown on it with your name to anyone signed in who can see the thing, unless whoever runs it hides it. Once a loan, a rental, a gift or a sale is accepted, the thing's history shows your name the same way (except for a gift or a sale marked as endless, which keeps no history). Whoever runs a group can also download its calendar, with the name on each reservation, loan or rental. Your email reaches the other side only when you write to them: a message you send to a group's members, or a reminder to return something, lets whoever receives it reply to you, so they see your address. Your profile (public name, bio, about and photo) is seen by the people who share a group with you, never your email, your language or your demographic details. Whoever runs a group can have a page in it with the name of their organisation, a logo, an introduction and a contact (and, in a network, the address and hours of their pickup point): it is seen together with the group, also without an account if the group is public. If someone invites you by email, the group keeps for a year a fingerprint of your address (not the address) so as not to invite you again; it is deleted after that year.

**Cookies:** technical only (session and security). There are no third-party or advertising cookies, which is why there is no banner.

**Deleting your account:** from your profile (Edit profile → Delete account), with email confirmation. It is immediate and irreversible: your account, your collections, your things and their photos, and your requests are erased. Questions you asked on other people's things and the transfer history stay **without your name** ("Former member").

**Getting a copy of your data:** also self-service, from your profile — download everything as one file, any time, no confirmation needed. If you manage a group, you can download the whole thing too: members, things, the full history. That second file carries other people's data, so keep it safe and don't forward it.

# Basic terms

OIUEEI is in alpha and offered "as is", without warranties, to the extent the law allows. The content you publish is yours and you are responsible for it; don't publish anything illegal or harmful. Exchanges (gifts, sales, loans, rentals, on-site reservations) are agreements between people: the platform is not a party to them and processes no payments — a deposit shown on a listing is information the two people agree between themselves, and OIUEEI never holds it, moves it or guarantees its return. There is a report button, and the operator may remove content that breaks these rules.

# For operators (self-hosting)

If you deploy OIUEEI, you are the data controller: complete this page with your identity, your purposes and your processors (email provider, object storage, hosting), and honour your users' rights. The EUPL-1.2 licence allows production use; what it asks in return is reciprocity — if you run a modified OIUEEI as a service, its source is owed to your users under the same licence.
`;
