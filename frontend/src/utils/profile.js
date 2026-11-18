const isEmpty = (value) => !String(value ?? '').trim();

/** Nobody can tell who this account is: the name is empty. A nickname is enough. */
export function hasNoName(me) {
  return isEmpty(me?.name);
}

/**
 * The profile is worth asking the person to complete: no name, **or** neither of the
 * two demographic fields (`age_range`, `postal_code`) filled in. One of the two is
 * enough, and the language does not count: every account has one. An account that has
 * not been read yet (`null`) is not incomplete: nothing is asked of it.
 */
export function profileIncomplete(me) {
  if (!me) return false;
  return hasNoName(me) || (isEmpty(me.age_range) && isEmpty(me.postal_code));
}
