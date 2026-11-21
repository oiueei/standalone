import { screen } from '@testing-library/react';
import { settle } from './settle';

/**
 * The request page is ready when its title is up AND the calendar (and whatever
 * else it asked for) has answered. That answer sets state after the title, and a
 * test that ends before it lands is reported as an update outside `act`; with
 * `axe` awaited, it lands in the middle of the run.
 *
 * `title` is a text or a regular expression of the page's heading (or any label
 * only the loaded page has); `apiFetch` is the file's mock of the network.
 */
export async function requestPageReady(apiFetch, title) {
  await screen.findByText(title);
  await settle(apiFetch);
}
