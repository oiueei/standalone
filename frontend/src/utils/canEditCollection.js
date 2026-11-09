/**
 * Whether this account may open the collection's settings: a curator, and in a
 * **network** only its founder (each dinamizador edits their own point instead).
 * One rule for the hero's pencil (and the "General" page behind it) and for the settings
 * pages themselves, which send anyone else back to the collection. The server stays the
 * one that decides; this only avoids offering a page it would refuse.
 */
export function canEditCollection(collection, userCode) {
  if (!collection || !collection.is_curator) return false;
  return collection.mode !== 'NETWORK' || (!!userCode && collection.owner === userCode);
}
