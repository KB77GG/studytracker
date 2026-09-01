(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.renderTaskAssignmentMatrix = factory();
  }
}(typeof window !== 'undefined' ? window : globalThis, function () {
  function escapeText(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  function statusText(result) {
    if (result.status === 'not_assigned') return '未布置';
    if (result.status === 'unable_to_determine') return '无法自动判断';
    return result.status_label || '已布置';
  }

  function rowMarkup(studentName, row) {
    var match = row.match || null;
    if (!match) {
      return '<div class="history-student-result is-new">'
        + '<div><strong>' + escapeText(studentName) + ' · ' + escapeText(row.unit_label || row.unit_id || '题组') + '</strong>'
        + '<span>未布置</span></div>'
        + '<small>该题组尚未发现历史任务，可直接发布。</small>'
        + '</div>';
    }
    var overlapType = row.overlap_type || match.overlap_type;
    var blocking = ['pending', 'progress', 'in_progress'].indexOf(match.status) >= 0 && overlapType === 'exact';
    var overlapLabel = overlapType === 'partial' ? '部分重复' : '完全重复';
    return '<div class="history-student-result' + (blocking ? ' is-blocking' : ' is-warning') + '">'
      + '<div><strong>' + escapeText(studentName) + ' · ' + escapeText(row.unit_label || row.unit_id || '题组') + '</strong>'
      + '<span>' + escapeText(match.status_label) + ' · ' + overlapLabel + '</span></div>'
      + '<small>原任务 #' + escapeText(match.task_id) + ' · 布置日期 ' + escapeText(match.assigned_date)
      + ' · 重叠' + escapeText(row.unit_label || row.unit_id || match.overlap_label || '题组')
      + ' · <a href="' + escapeText(match.view_url) + '" target="_blank" rel="noopener">查看原任务</a></small>'
      + '</div>';
  }

  function fallbackQuestionTypeRows(student, result) {
    var matches = student.matches || [];
    return (result.resource && result.resource.units || []).map(function (unit) {
      var unitMatches = matches.filter(function (match) {
        return (match.overlap_units || []).indexOf(unit.id) >= 0;
      });
      return {
        unit_id: unit.id,
        unit_label: unit.label || unit.id,
        match: unitMatches[0] || null
      };
    });
  }

  function duplicateErrorMessage(error) {
    if (error === 'duplicate_assignment_conflict') {
      return '检测到重复任务：请查看下方历史记录；如需复训，请二次确认并填写原因。';
    }
    return '';
  }

  var renderTaskAssignmentMatrix = function (result) {
    return (result.students || []).map(function (student) {
      var isQuestionType = result.resource && result.resource.kind === 'question_type';
      var rows = isQuestionType
        ? (Array.isArray(student.matrix_rows) ? student.matrix_rows : fallbackQuestionTypeRows(student, result))
        : null;
      if (isQuestionType && rows.length) {
        return rows.map(function (row) { return rowMarkup(student.student_name, row); });
      }
      var matches = student.matches || [];
      if (!matches.length) {
        return ['<div class="history-student-result">'
          + '<div><strong>' + escapeText(student.student_name) + ' · 选定资源</strong><span>' + escapeText(statusText(student)) + '</span></div>'
          + '<small>' + (student.status === 'unable_to_determine'
            ? '该任务没有稳定题目身份，系统不会误标为未布置。'
            : '当前资源对该学生尚未发现历史记录。') + '</small></div>'];
      }
      return matches.reduce(function (markup, match) {
        var units = match.overlap_units && match.overlap_units.length ? match.overlap_units : [match.overlap_label || '完整资源'];
        return markup.concat(units.map(function (unit) {
          return rowMarkup(student.student_name, { unit_id: unit, unit_label: unit, match: match });
        }));
      }, []);
    }).reduce(function (all, rows) { return all.concat(rows); }, []).join('');
  };

  renderTaskAssignmentMatrix.duplicateErrorMessage = duplicateErrorMessage;
  return renderTaskAssignmentMatrix;
}));
