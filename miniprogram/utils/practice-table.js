function isCoordinate(value) {
    return Array.isArray(value) && value.length === 2 && value.every(Number.isInteger)
}

function fallbackLayout(table) {
    const source = Array.isArray(table && table.content) ? table.content : []
    const nestedHeaderRows = new Set()
    const rows = source.map((row, rowIndex) => {
        let cells = Array.isArray(row) ? row.slice() : [row]
        if (cells.length === 1 && Array.isArray(cells[0]) && !isCoordinate(cells[0])) {
            nestedHeaderRows.add(rowIndex)
            cells = cells[0].slice()
        }
        if (cells.length > 1 && !isCoordinate(cells[0])
            && cells.slice(1).every(isCoordinate)
            && cells.slice(1).some(cell => cell[0] < rowIndex)) {
            cells = [cells[0], ...cells.slice(1).map(() => [rowIndex, 0])]
        }
        return cells
    })
    const columnCount = rows.reduce((maximum, row) => Math.max(maximum, row.length), 0)
    rows.forEach((row, rowIndex) => {
        if (row.length === 1 && columnCount > 1 && rowIndex === 0) {
            while (row.length < columnCount) row.push([0, 0])
        } else {
            while (row.length < columnCount) row.push('')
        }
    })

    function resolve(rowIndex, columnIndex, trail) {
        const value = rows[rowIndex] && rows[rowIndex][columnIndex]
        if (!isCoordinate(value)) return `${rowIndex}:${columnIndex}`
        const target = `${value[0]}:${value[1]}`
        const seen = new Set(trail || [])
        if (seen.has(target) || !rows[value[0]] || value[1] >= columnCount) {
            return `${rowIndex}:${columnIndex}`
        }
        seen.add(`${rowIndex}:${columnIndex}`)
        return resolve(value[0], value[1], seen)
    }

    const positions = new Map()
    rows.forEach((row, rowIndex) => row.forEach((_cell, columnIndex) => {
        const origin = resolve(rowIndex, columnIndex)
        if (!positions.has(origin)) positions.set(origin, [])
        positions.get(origin).push([rowIndex, columnIndex])
    }))

    const renderRows = rows.map(() => [])
    positions.forEach((slots, origin) => {
        const [rowIndex, columnIndex] = origin.split(':').map(Number)
        const value = rows[rowIndex][columnIndex]
        const minRow = Math.min(...slots.map(slot => slot[0]))
        const maxRow = Math.max(...slots.map(slot => slot[0]))
        const minColumn = Math.min(...slots.map(slot => slot[1]))
        const maxColumn = Math.max(...slots.map(slot => slot[1]))
        const rectangular = slots.length === (maxRow - minRow + 1) * (maxColumn - minColumn + 1)
            && rowIndex === minRow && columnIndex === minColumn
        const text = isCoordinate(value) ? '' : String(value == null ? '' : value)
        const colspan = rectangular ? maxColumn - minColumn + 1 : 1
        const rowspan = rectangular ? maxRow - minRow + 1 : 1
        renderRows[rowIndex].push({
            key: `r${rowIndex}c${columnIndex}`,
            row_index: rowIndex,
            column_index: columnIndex,
            text,
            rowspan,
            colspan,
            is_header: /<\s*(?:b|bc)\s*>/i.test(text)
                || nestedHeaderRows.has(rowIndex)
                || (rowIndex === 0 && colspan === columnCount && columnCount > 1)
        })
    })
    return { version: 1, column_count: columnCount, rows: renderRows }
}

function tableLayout(table) {
    const normalized = table && table.render && Number(table.render.version) === 1
        ? table.render
        : fallbackLayout(table || {})
    const columnCount = Math.max(1, Number(normalized.column_count) || 1)
    const minimumWidth = Math.max(680, columnCount * 168)
    const cells = []
    ;(normalized.rows || []).forEach(row => {
        ;(row || []).forEach(cell => {
            const columnIndex = Number(cell.column_index) || 0
            const rowIndex = Number(cell.row_index) || 0
            const colspan = Math.max(1, Number(cell.colspan) || 1)
            const rowspan = Math.max(1, Number(cell.rowspan) || 1)
            cells.push({
                ...cell,
                cellKey: cell.key || `r${rowIndex}c${columnIndex}`,
                headerClass: cell.is_header ? 'is-header' : '',
                gridStyle: `grid-column: ${columnIndex + 1} / span ${colspan}; grid-row: ${rowIndex + 1} / span ${rowspan};`
            })
        })
    })
    return {
        columnCount,
        cells,
        tableStyle: `grid-template-columns: repeat(${columnCount}, minmax(168rpx, 1fr)); min-width: ${minimumWidth}rpx;`
    }
}

module.exports = { tableLayout }
