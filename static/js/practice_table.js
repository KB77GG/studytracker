(function practiceTableModule(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PracticeTable = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function buildPracticeTableApi() {
  'use strict';

  const inlineToken = /<\s*(\/?)\s*(b|i|bc|iu|br|divider)\b([^>]*)>|\$([^$\s]+)\$/gi;
  const structuredToken = /<\s*(\/?)\s*(b|i|bc|iu|br|divider|table|thead|tbody|tfoot|tr|th|td|caption|colgroup|col|p|div|ul|ol|li)\b([^>]*)>|\$([^$\s]+)\$/gi;
  const richTag = /<\s*\/?\s*(?:b|i|bc|iu|br|divider|table|thead|tbody|tfoot|tr|th|td|caption|colgroup|col|p|div|ul|ol|li)\b[^>]*>/gi;

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

  function attributeValue(source, name) {
    const pattern = new RegExp(
      `(?:^|\\s)${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s"'=<>]+))`,
      'i'
    );
    const match = pattern.exec(String(source || ''));
    return match ? String(match[1] ?? match[2] ?? match[3] ?? '') : '';
  }

  function spanAttribute(source, name, allowZero = false) {
    const raw = attributeValue(source, name);
    if (!/^\d+$/.test(raw)) return '';
    const value = Number(raw);
    if (allowZero && value === 0) return ` ${name}="0"`;
    return value >= 1 && value <= 100 ? ` ${name}="${value}"` : '';
  }

  function canonicalTag(closing, name, attributes) {
    const tag = String(name || '').toLowerCase();
    if (tag === 'br' || tag === 'divider') return '<br>';

    const inline = {
      b: ['<strong>', '</strong>'],
      i: ['<em>', '</em>'],
      bc: ['<span class="bc">', '</span>'],
      iu: ['<span class="iu">', '</span>']
    };
    if (inline[tag]) return inline[tag][closing ? 1 : 0];

    if (tag === 'table') {
      return closing
        ? '</table></div>'
        : '<div class="table-wrap practice-embedded-table-wrap"><table class="practice-table practice-embedded-table">';
    }
    if (tag === 'th' || tag === 'td') {
      if (closing) return `</${tag}>`;
      const rowspan = spanAttribute(attributes, 'rowspan', true);
      const colspan = spanAttribute(attributes, 'colspan');
      const rawScope = attributeValue(attributes, 'scope').toLowerCase();
      const scope = tag === 'th' && ['col', 'row', 'colgroup', 'rowgroup'].includes(rawScope)
        ? ` scope="${rawScope}"`
        : '';
      return `<${tag}${scope}${rowspan}${colspan}>`;
    }

    const block = {
      thead: ['<thead>', '</thead>'],
      tbody: ['<tbody>', '</tbody>'],
      tfoot: ['<tfoot>', '</tfoot>'],
      tr: ['<tr>', '</tr>'],
      caption: ['<caption>', '</caption>'],
      colgroup: ['<colgroup>', '</colgroup>'],
      col: [`<col${spanAttribute(attributes, 'span')}>`, ''],
      p: ['<p class="practice-richtext-block">', '</p>'],
      div: ['<div class="practice-richtext-block">', '</div>'],
      ul: ['<ul class="practice-richtext-list">', '</ul>'],
      ol: ['<ol class="practice-richtext-list">', '</ol>'],
      li: ['<li>', '</li>']
    };
    return block[tag] ? block[tag][closing ? 1 : 0] : '';
  }

  function structuralParent(stack) {
    for (let index = stack.length - 1; index >= 0; index -= 1) {
      if (!['b', 'i', 'bc', 'iu'].includes(stack[index])) return stack[index];
    }
    return '';
  }

  function canOpenStructuredTag(name, stack) {
    const parent = structuralParent(stack);
    const inlineParents = new Set(['', 'p', 'div', 'li', 'td', 'th', 'caption']);
    if (['b', 'i', 'bc', 'iu', 'br', 'divider'].includes(name)) {
      return inlineParents.has(parent);
    }
    if (name === 'table') return ['', 'div', 'li', 'td', 'th'].includes(parent);
    if (name === 'caption' || name === 'colgroup' || name === 'thead' || name === 'tbody' || name === 'tfoot') {
      return parent === 'table';
    }
    if (name === 'tr') return ['table', 'thead', 'tbody', 'tfoot'].includes(parent);
    if (name === 'td' || name === 'th') return parent === 'tr';
    if (name === 'col') return parent === 'colgroup';
    if (name === 'li') return parent === 'ul' || parent === 'ol';
    if (name === 'ul' || name === 'ol') return ['', 'div', 'li', 'td', 'th'].includes(parent);
    if (name === 'p') return ['', 'div', 'li', 'td', 'th'].includes(parent);
    if (name === 'div') return ['', 'div', 'li', 'td', 'th'].includes(parent);
    return false;
  }

  function closeOptionalTags(stack, names) {
    let html = '';
    while (names.includes(structuralParent(stack))) {
      while (['b', 'i', 'bc', 'iu'].includes(stack[stack.length - 1])) {
        html += canonicalTag(true, stack.pop(), '');
      }
      html += canonicalTag(true, stack.pop(), '');
    }
    return html;
  }

  function prepareStructuredOpen(name, stack) {
    let html = '';
    if (['td', 'th', 'tr', 'thead', 'tbody', 'tfoot'].includes(name)) {
      html += closeOptionalTags(stack, ['p']);
    }
    if (['caption', 'thead', 'tbody', 'tfoot', 'tr'].includes(name)) {
      html += closeOptionalTags(stack, ['colgroup']);
    }
    if (name === 'td' || name === 'th') html += closeOptionalTags(stack, ['td', 'th']);
    if (name === 'tr') {
      html += closeOptionalTags(stack, ['td', 'th']);
      html += closeOptionalTags(stack, ['tr']);
    }
    if (['thead', 'tbody', 'tfoot'].includes(name)) {
      html += closeOptionalTags(stack, ['td', 'th']);
      html += closeOptionalTags(stack, ['tr']);
      html += closeOptionalTags(stack, ['thead', 'tbody', 'tfoot']);
    }
    if (name === 'li') html += closeOptionalTags(stack, ['li']);
    if (['p', 'div', 'ul', 'ol', 'table'].includes(name)) {
      html += closeOptionalTags(stack, ['p']);
    }
    return html;
  }

  function prepareStructuredClose(name, stack) {
    let html = '';
    if (['td', 'th', 'tr', 'thead', 'tbody', 'tfoot', 'table'].includes(name)) {
      html += closeOptionalTags(stack, ['p']);
    }
    if (name === 'tr') html += closeOptionalTags(stack, ['td', 'th']);
    if (['thead', 'tbody', 'tfoot'].includes(name)) {
      html += closeOptionalTags(stack, ['td', 'th']);
      html += closeOptionalTags(stack, ['tr']);
    }
    if (name === 'table') {
      html += closeOptionalTags(stack, ['td', 'th']);
      html += closeOptionalTags(stack, ['tr']);
      html += closeOptionalTags(stack, ['thead', 'tbody', 'tfoot', 'colgroup']);
    }
    if (name === 'ul' || name === 'ol') html += closeOptionalTags(stack, ['li']);
    return html;
  }

  function renderTextSegment(value, stack, allowStructure) {
    if (
      allowStructure
      && !String(value || '').trim()
      && ['table', 'thead', 'tbody', 'tfoot', 'tr', 'colgroup'].includes(structuralParent(stack))
    ) return '';
    return escapeHtml(value).replace(/\n/g, '<br>');
  }

  function renderRichText(value, placeholderReplacer, allowStructure = false) {
    const raw = decodeKnownEntities(value);
    const tokenPattern = allowStructure ? structuredToken : inlineToken;
    let html = '';
    let last = 0;
    const stack = [];
    raw.replace(tokenPattern, (match, closing, tag, attributes, placeholderId, offset) => {
      html += renderTextSegment(raw.slice(last, offset), stack, allowStructure);
      if (placeholderId !== undefined) {
        html += typeof placeholderReplacer === 'function'
          ? placeholderReplacer(String(placeholderId), match)
          : escapeHtml(match);
      } else {
        const name = String(tag || '').toLowerCase();
        if (closing) {
          if (allowStructure) html += prepareStructuredClose(name, stack);
          if (stack[stack.length - 1] === name) html += canonicalTag(true, stack.pop(), '');
          else html += escapeHtml(match);
        } else {
          const isVoid = name === 'br' || name === 'divider' || name === 'col';
          const selfClosing = /\/\s*$/.test(String(attributes || ''));
          if (allowStructure) html += prepareStructuredOpen(name, stack);
          if (allowStructure && !canOpenStructuredTag(name, stack)) {
            html += escapeHtml(match);
          } else {
            html += canonicalTag(false, name, attributes);
            if (!isVoid && !selfClosing) stack.push(name);
            if (!isVoid && selfClosing) html += canonicalTag(true, name, '');
          }
        }
      }
      last = offset + match.length;
      return match;
    });
    html += renderTextSegment(raw.slice(last), stack, allowStructure);
    while (stack.length) html += canonicalTag(true, stack.pop(), '');
    return html;
  }

  function richText(value) {
    return renderRichText(value);
  }

  function withPlaceholders(value, replacer) {
    return renderRichText(value, replacer);
  }

  function withStructuredPlaceholders(value, replacer) {
    return renderRichText(value, replacer, true);
  }

  function unmappedItems(items, seenIds) {
    const seen = seenIds instanceof Set ? seenIds : new Set(seenIds || []);
    return (Array.isArray(items) ? items : []).filter((item) => {
      const key = item && (item.id ?? item.number);
      return key !== undefined && key !== null && !seen.has(String(key));
    });
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
      .replace(richTag, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  return {
    escapeHtml,
    layout,
    plainText,
    richText,
    unmappedItems,
    withPlaceholders,
    withStructuredPlaceholders
  };
}));
