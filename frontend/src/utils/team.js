/**
 * What one member of the team is called in this group: the `display_name` of their page
 * there (`points`: the entity's name, else their account's), and the account's own name
 * where they have no page. `''` when they have neither.
 */
export function teamMemberName(collection, member) {
  const card = (collection.points ?? []).find((point) => point.user === member.code);
  return card ? card.display_name : member.name;
}

/**
 * Who runs a collection, in the one order and with the one rule every place that
 * names them follows: the founder first, then the co-curators; those with a name
 * are named, those without are only counted — at the end.
 *
 * Each is called by the name of their page in the group (`teamMemberName`).
 *
 * The API sends a person's bare `name`, never an email standing in for it (the
 * email is withheld from co-members), so someone who set none arrives as
 * `''`. Listing them would leave a gap — "Oriol, ," — so they are counted
 * instead ("2 more people", `collectionPage.curatorsMore`), the founder
 * included. And with nobody named there is nothing to say at all.
 *
 * `CollectionPage`'s "Run by:" line (which links each name) and the "Run by"
 * column of "My groups" on the own profile (plain text) both read it, so the two
 * cannot come to disagree about who is on the team or how it is written.
 */
export function collectionTeam(collection) {
  const team = [
    { code: collection.owner, name: collection.owner_name },
    ...(collection.co_owners ?? []),
  ].map((member) => ({ ...member, name: teamMemberName(collection, member) }));
  const named = team.filter((member) => member.name);
  return { named, unnamedCount: team.length - named.length };
}

// The list formatter of the language on screen. A tag the browser cannot make
// sense of is a RangeError; the reader's default language stands in rather than
// a page that does not render.
function listFormatter(language) {
  const options = { style: 'long', type: 'conjunction' };
  try {
    return new Intl.ListFormat(language, options);
  } catch {
    return new Intl.ListFormat(undefined, options);
  }
}

/**
 * Words written as the language writes a list: "A, B y C". The same browser
 * formatter the team line uses (`Intl.ListFormat`), for any list of names.
 */
export function formatList(words, language) {
  return listFormatter(language).format(words);
}

/**
 * The team as the pieces of one sentence, written as the language writes a list:
 * "Lala y Lele", "Lala, Lele y Lili" in Spanish, "A i B" / "A, B i C" in Catalan, "A and B" / "A, B, and C" in English.
 * The conjunction and the commas are the browser's own (`Intl.ListFormat`, in the
 * language that i18n has on screen), not ours: the Oxford comma of English, and the
 * Spanish "e" before a name that begins with "i", are written without us knowing.
 *
 * **Whoever has no name is the last element of the list**, so the sentence reads
 * "Lala, Lele y 2 personas más" and the text of `curatorsMore` carries no
 * conjunction of its own ("2 personas más", not "y 2 personas más" — it would say it
 * twice). With nobody named: `[]`.
 *
 * Each piece is `{ type: 'member', member }` (a name with its `code`, for the page
 * to link), `{ type: 'more', text }` (the count of those without a name) or
 * `{ type: 'literal', value }` (what the language puts between them). The hero
 * renders them one by one, with a `Link` for each member; `teamText` joins them.
 */
export function teamParts(collection, t, language) {
  const { named, unnamedCount } = collectionTeam(collection);
  if (named.length === 0) return [];
  const elements = named.map((member) => ({ type: 'member', member }));
  if (unnamedCount > 0) {
    elements.push({
      type: 'more',
      text: t('collectionPage.curatorsMore', { count: unnamedCount }),
    });
  }
  const words = elements.map((element) =>
    element.type === 'member' ? element.member.name : element.text
  );
  // The pieces come back in order, so the n-th `element` is the n-th word we gave
  // it — matching them by their text would confuse two people with the same name.
  let next = 0;
  return listFormatter(language)
    .formatToParts(words)
    .map((part) =>
      part.type === 'element' ? elements[next++] : { type: 'literal', value: part.value }
    );
}

/**
 * The team as one line of plain text — "Oriol, Lili y 2 personas más" — or `''`
 * when nobody has a name. The same words as the hero's line, minus the links.
 */
export function teamText(collection, t, language) {
  return teamParts(collection, t, language)
    .map((part) => {
      if (part.type === 'member') return part.member.name;
      if (part.type === 'more') return part.text;
      return part.value;
    })
    .join('');
}
