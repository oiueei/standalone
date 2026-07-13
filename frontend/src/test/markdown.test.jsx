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

  test('renders pipe tables with a scroll wrapper', () => {
    const result = markdownToHtml(
      '| Día | Horario |\n|---|---|\n| Lunes - Viernes | 09:00 - 14:00 |\n| Domingo | Cerrado |'
    );
    expect(result).toContain('class="markdown-table-wrap"');
    expect(result).toContain('<table><thead><tr><th>Día</th><th>Horario</th></tr></thead>');
    expect(result).toContain('<td>Lunes - Viernes</td>');
    expect(result).toContain('<td>Domingo</td><td>Cerrado</td>');
  });

  test('table cells render inline markdown and stay HTML-escaped', () => {
    const result = markdownToHtml('| A | B |\n|---|---|\n| **bold** | <script>alert(1)</script> |');
    expect(result).toContain('<td><strong>bold</strong></td>');
    expect(result).not.toContain('<script>');
    expect(result).toContain('&lt;script&gt;');
  });

  test('a pipe line without a separator row is not a table', () => {
    const result = markdownToHtml('| just | text |\nplain line');
    expect(result).not.toContain('<table>');
    expect(result).toContain('| just | text |');
  });

  test('text after a table resumes normal rendering', () => {
    const result = markdownToHtml('| A |\n|---|\n| x |\nAfter');
    expect(result).toContain('</table></div>');
    expect(result).toContain('<span>After</span>');
  });

  test('renders # / ## / ### as h3 / h4 / h5', () => {
    expect(markdownToHtml('# Título')).toBe('<h3>Título</h3>');
    expect(markdownToHtml('## Título')).toBe('<h4>Título</h4>');
    expect(markdownToHtml('### Título')).toBe('<h5>Título</h5>');
  });

  test('deeper heading levels cap at h5', () => {
    expect(markdownToHtml('#### Título')).toBe('<h5>Título</h5>');
    expect(markdownToHtml('###### Título')).toBe('<h5>Título</h5>');
  });

  test('a heading escapes HTML and still renders inline markdown', () => {
    const result = markdownToHtml('# **Bold** <script>alert(1)</script>');
    expect(result).toBe('<h3><strong>Bold</strong> &lt;script&gt;alert(1)&lt;/script&gt;</h3>');
    expect(result).not.toContain('<script>');
  });

  test('a heading between paragraphs does not disturb the surrounding text', () => {
    const result = markdownToHtml('Before\n## Título\nAfter');
    expect(result).toBe('<span>Before</span><h4>Título</h4><span>After</span>');
  });

  test('a heading closes an open list', () => {
    const result = markdownToHtml('- Item\n# Título');
    expect(result).toBe('<ul><li>Item</li></ul><h3>Título</h3>');
  });

  test('a bare # with no text is not treated as a heading', () => {
    const result = markdownToHtml('#');
    expect(result).not.toContain('<h3>');
    expect(result).toContain('#');
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
