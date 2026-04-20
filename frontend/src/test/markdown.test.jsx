import { describe, test, expect } from 'vitest';
import { render } from '@testing-library/react';
import MarkdownText, { markdownToHtml } from '../components/MarkdownText';

describe('markdownToHtml', () => {
  test('renders bold text', () => {
    expect(markdownToHtml('Hello **world**')).toContain('<strong>world</strong>');
  });

  test('renders italic with asterisks', () => {
    expect(markdownToHtml('Hello *world*')).toContain('<em>world</em>');
  });

  test('renders italic with underscores', () => {
    expect(markdownToHtml('Hello _world_')).toContain('<em>world</em>');
  });

  test('renders links with safe URLs', () => {
    const result = markdownToHtml('[Click here](https://example.com)');
    expect(result).toContain('href="https://example.com"');
    expect(result).toContain('>Click here</a>');
  });

  test('rejects javascript: URLs', () => {
    const result = markdownToHtml('[Click](javascript:alert(1))');
    expect(result).toContain('href="#"');
    expect(result).not.toContain('javascript:');
  });

  test('rejects data: URLs', () => {
    const result = markdownToHtml('[Click](data:text/html,<h1>XSS</h1>)');
    expect(result).toContain('href="#"');
  });

  test('renders unordered lists', () => {
    const result = markdownToHtml('- Item one\n- Item two');
    expect(result).toContain('<ul>');
    expect(result).toContain('<li>Item one</li>');
    expect(result).toContain('<li>Item two</li>');
    expect(result).toContain('</ul>');
  });

  test('renders ordered lists', () => {
    const result = markdownToHtml('1. First\n2. Second');
    expect(result).toContain('<ol>');
    expect(result).toContain('<li>First</li>');
    expect(result).toContain('<li>Second</li>');
    expect(result).toContain('</ol>');
  });

  test('escapes HTML tags in input', () => {
    const result = markdownToHtml('<script>alert("xss")</script>');
    expect(result).not.toContain('<script>');
    expect(result).toContain('&lt;script&gt;');
  });

  test('handles nested bold and italic', () => {
    const result = markdownToHtml('**bold *italic* bold**');
    expect(result).toContain('<strong>');
    expect(result).toContain('<em>italic</em>');
  });

  test('handles empty input', () => {
    expect(markdownToHtml('')).toBe('');
    expect(markdownToHtml(null)).toBe('');
    expect(markdownToHtml(undefined)).toBe('');
  });

  test('handles plain text without markdown', () => {
    const result = markdownToHtml('Just plain text');
    expect(result).toContain('Just plain text');
    expect(result).not.toContain('<strong>');
    expect(result).not.toContain('<em>');
  });

  test('handles mixed lists and text', () => {
    const result = markdownToHtml('Header\n- Item\nFooter');
    expect(result).toContain('<ul>');
    expect(result).toContain('<li>Item</li>');
    expect(result).toContain('</ul>');
    expect(result).toContain('Header');
    expect(result).toContain('Footer');
  });
});

describe('MarkdownText component', () => {
  test('renders null for empty text', () => {
    const { container } = render(<MarkdownText text="" />);
    expect(container.innerHTML).toBe('');
  });

  test('renders markdown content', () => {
    const { container } = render(<MarkdownText text="**Hello** world" />);
    expect(container.querySelector('strong').textContent).toBe('Hello');
  });

  test('applies className prop', () => {
    const { container } = render(<MarkdownText text="Test" className="custom" />);
    expect(container.querySelector('.markdown-text.custom')).toBeTruthy();
  });
});
