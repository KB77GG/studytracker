(function practiceTableModule(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PracticeTable = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function buildPracticeTableApi() {
  'use strict';

  const allowedTag = /<\s*(\/?)\s*(b|i|bc|iu)\s*>|<\s*(br|divider)\s*\/?\s*>/gi;

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function decodeKnownEntities(value) {
    return String(value == null ? '' : value)
      .replace(/&nbsp;|&#160;/gi, ' ')
      .replace(/&lt;/gi, '<')
      .replace(/&gt;/gi, '>')
      .replace(/&quot;/gi, '"')
      .replace(/&#39;|&apos;/gi, "'")
      .replace(/&amp;/gi, '&');
  }

  function richText(value) {
    const tokens = [];
    const tokenized = decodeKnownEntities(value).replace(
      allowedTag,
      (_match, closing, name, lineBreak) => {
        let html = '<br>';
        if (!lineBreak) {
          const tag = String(name || '').toLowerCase();
          if (tag === 'b') html = closing ? '</strong>' : '<strong>';
          if (tag === 'i') html = closing ? '</em>' : '<em>';
          if (tag === 'bc') html = closing ? '</span>' : '<span class="bc">';
          if (tag === 'iu') html = closing ? '</span>' : '<span class="iu">';
        }
        const index = tokens.push(html) - 1;
        return `\uE000${index}\uE001`;
      }
    );
    let html = escapeHtml(tokenized).replace(/\n/g, '<br>');
    html = html.replace(/\uE000(\d+)\uE001/g, (_match, index) => tokens[Number(index)] || '');
    return html;
  }

  function withPlaceholders(value, replacer) {
    const raw = String(value == null ? '' : value);
    let html = '';
    let last = 0;
    raw.replace(/\$([^$\s]+)\$/g, (match, id, offset) => {
      html += richText(raw.slice(last, offset));
      html += replacer(String(id), match);
      last = offset + match.length;
      return match;
    });
    html += richText(raw.slice(last));
    return html;
  }

  function isCoordinate(value) {
    return Array.isArray(value) && value.length === 2 && value.every(Number.isInteger);
  }

  function fallbackLayout(table) {
    const source = Array.isArray(table && table.content) ? table.content : [];
    const nestedHeaderRows = new Set();
    const rows = source.map((row, rowIndex) => {
      let cells = Array.isArray(row) ? row.slice() : [row];
      if (cells.length === 1 && Array.isArray(cells[0]) && !isCoordinate(cells[0])) {
        nestedHeaderRows.add(rowIndex);
        cells = cells[0].slice();
      }
      if (cells.length > 1 && !isCoordinate(cells[0])
        && cells.slice(1).every(isCoordinate)
        && cells.slice(1).some((cell) => cell[0] < rowIndex)) {
        cells = [cells[0], ...cells.slice(1).map(() => [rowIndex, 0])];
      }
      return cells;
    });
    const columnCount = rows.reduce((maximum, row) => Math.max(maximum, row.length), 0);
    rows.forEach((row, rowIndex) => {
      if (row.length === 1 && columnCount > 1 && rowIndex === 0) {
        while (row.length < columnCount) row.push([0, 0]);
      } else {
        while (row.length < columnCount) row.push('');
      }
    });

    function resolve(rowIndex, columnIndex, trail) {
      const value = rows[rowIndex] && rows[rowIndex][columnIndex];
      if (!isCoordinate(value)) return `${rowIndex}:${columnIndex}`;
      const key = `${value[0]}:${value[1]}`;
      const seen = new Set(trail || []);
      if (seen.has(key) || !rows[value[0]] || value[1] >= columnCount) return `${rowIndex}:${columnIndex}`;
      seen.add(`${rowIndex}:${columnIndex}`);
      return resolve(value[0], value[1], seen);
    }

    const positions = new Map();
    rows.forEach((row, rowIndex) => row.forEach((_cell, columnIndex) => {
      const origin = resolve(rowIndex, columnIndex);
      if (!positions.has(origin)) positions.set(origin, []);
      positions.get(origin).push([rowIndex, columnIndex]);
    }));

    const renderRows = rows.map(() => []);
    const headerRows = new Set(rows.map((row, rowIndex) => {
      const texts = row.filter((value) => !isCoordinate(value) && String(value == null ? '' : value).trim());
      return texts.length >= 2 && texts.every((value) => /<\s*(?:b|bc)\s*>/i.test(String(value))) ? rowIndex : -1;
    }).filter((rowIndex) => rowIndex >= 0));
    positions.forEach((slots, origin) => {
      const [rowIndex, columnIndex] = origin.split(':').map(Number);
      const value = rows[rowIndex][columnIndex];
      const minRow = Math.min(...slots.map((slot) => slot[0]));
      const maxRow = Math.max(...slots.map((slot) => slot[0]));
      const minColumn = Math.min(...slots.map((slot) => slot[1]));
      const maxColumn = Math.max(...slots.map((slot) => slot[1]));
      const rectangular = slots.length === (maxRow - minRow + 1) * (maxColumn - minColumn + 1)
        && rowIndex === minRow && columnIndex === minColumn;
      const text = isCoordinate(value) ? '' : String(value == null ? '' : value);
      const colspan = rectangular ? maxColumn - minColumn + 1 : 1;
      const rowspan = rectangular ? maxRow - minRow + 1 : 1;
      const isHeader = /<\s*(?:b|bc)\s*>/i.test(text)
        || nestedHeaderRows.has(rowIndex)
        || (rowIndex === 0 && colspan === columnCount && columnCount > 1);
      renderRows[rowIndex].push({
        key: `r${rowIndex}c${columnIndex}`,
        row_index: rowIndex,
        column_index: columnIndex,
        text,
        rowspan,
        colspan,
        is_header: isHeader,
        scope: isHeader ? (colspan > 1 ? 'colgroup' : ((headerRows.has(rowIndex) || nestedHeaderRows.has(rowIndex)) ? 'col' : (columnIndex === 0 ? 'row' : ''))) : ''
      });
    });
    return { version: 1, column_count: columnCount, rows: renderRows };
  }

  function layout(table) {
    const render = table && table.render;
    if (render && Number(render.version) === 1 && Array.isArray(render.rows)) return render;
    return fallbackLayout(table || {});
  }

  function plainText(value) {
    return decodeKnownEntities(value)
      .replace(allowedTag, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  return { escapeHtml, layout, plainText, richText, withPlaceholders };
}));
