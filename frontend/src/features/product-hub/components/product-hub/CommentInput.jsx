import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Avatar, AvatarFallback } from '@/shared/components/ui/avatar';
import { Send, Loader2, AtSign, Pencil, Trash2, X, Check } from 'lucide-react';
import { useAuth } from '@/shared/contexts/AuthContext';

function useMentionableUsers(isAdmin) {
  const { api } = useAuth();
  const [users, setUsers] = useState([]);
  useEffect(() => {
    if (!isAdmin || !api) return;
    api.get('/product-hub/mentionable-users')
      .then(res => setUsers(res.data.users || []))
      .catch(err => { if (process.env.NODE_ENV === 'development') console.warn('Failed to fetch mentionable users:', err.message); });
  }, [isAdmin, api]);
  return users;
}

function MentionDropdown({ users, search, activeIndex, onSelect, listRef }) {
  const filtered = users.filter(u => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
  });

  if (filtered.length === 0) {
    return (
      <div className="absolute z-50 bottom-full mb-1 right-0 w-72 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden hub-mention-dropdown">
        <div className="p-2 border-b border-slate-100 flex items-center gap-1.5">
          <AtSign className="h-3 w-3 text-brand-turquoise" />
          <span className="text-[10px] text-muted-foreground">إشارة إلى مستخدم</span>
        </div>
        <div className="p-4 text-center text-xs text-muted-foreground">
          لا يوجد مستخدمون متاحون للإشارة
        </div>
      </div>
    );
  }

  return (
    <div
      ref={listRef}
      className="absolute z-50 bottom-full mb-1 right-0 w-72 max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-lg hub-mention-dropdown"
    >
      <div className="p-2 border-b border-slate-100 flex items-center gap-1.5">
        <AtSign className="h-3 w-3 text-brand-turquoise" />
        <span className="text-[10px] text-muted-foreground">إشارة إلى مستخدم</span>
      </div>
      {filtered.map((u, i) => (
        <button
          key={u.id}
          data-active={i === activeIndex}
          onMouseDown={(e) => { e.preventDefault(); onSelect(u); }}
          className={`w-full flex items-center gap-2.5 p-2.5 text-right transition-colors duration-120 ${
            i === activeIndex ? 'bg-brand-turquoise/10' : 'hover:bg-slate-50'
          }`}
        >
          <Avatar className="h-7 w-7 flex-shrink-0">
            <AvatarFallback className="bg-brand-navy text-white text-[10px]">
              {(u.name || '?')[0]}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0 text-right">
            <p className="text-xs font-semibold text-foreground truncate">{u.name}</p>
            <p className="text-[10px] text-muted-foreground truncate ltr">{u.email}</p>
          </div>
          {u.role && (
            <span className="text-[9px] text-muted-foreground bg-slate-100 px-1.5 py-0.5 rounded flex-shrink-0">
              {u.role === 'platform_admin' ? 'مدير' : 'فريق'}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function getMentionAtPos(text, cursorPos) {
  const before = text.slice(0, cursorPos);
  const atIdx = before.lastIndexOf('@');
  if (atIdx === -1) return null;
  const afterAt = before.slice(atIdx + 1);
  if (afterAt.includes('\n')) return null;
  if (afterAt.length > 40) return null;
  return { start: atIdx, search: afterAt };
}

function useCommentMentions(mentionableUsers) {
  const [text, setText] = useState('');
  const [showMentions, setShowMentions] = useState(false);
  const [mentionSearch, setMentionSearch] = useState('');
  const [mentionIndex, setMentionIndex] = useState(0);
  const [cursorPos, setCursorPos] = useState(0);
  const [mentionedUsers, setMentionedUsers] = useState([]);
  const textareaRef = useRef(null);
  const mentionListRef = useRef(null);

  const filteredUsers = mentionableUsers.filter(u => {
    if (!mentionSearch) return true;
    const q = mentionSearch.toLowerCase();
    return (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
  });

  const handleChange = (e) => {
    const val = e.target.value;
    const pos = e.target.selectionStart;
    setText(val);
    setCursorPos(pos);

    const mention = getMentionAtPos(val, pos);
    if (mention !== null) {
      setMentionSearch(mention.search);
      setShowMentions(true);
      setMentionIndex(0);
    } else {
      setShowMentions(false);
    }
  };

  const insertMention = useCallback((user) => {
    const mention = getMentionAtPos(text, cursorPos);
    if (!mention) return;

    const before = text.slice(0, mention.start);
    const after = text.slice(cursorPos);
    const mentionText = `@${user.name} `;
    const newText = before + mentionText + after;
    setText(newText);
    setShowMentions(false);
    setMentionedUsers(prev => {
      if (prev.find(m => m.id === user.id)) return prev;
      return [...prev, { id: user.id, name: user.name, email: user.email }];
    });

    requestAnimationFrame(() => {
      if (textareaRef.current) {
        const newPos = mention.start + mentionText.length;
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newPos, newPos);
        setCursorPos(newPos);
      }
    });
  }, [text, cursorPos]);

  const handleKeyDown = useCallback((e) => {
    if (showMentions && filteredUsers.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex(prev => Math.min(prev + 1, filteredUsers.length - 1));
        return true;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex(prev => Math.max(prev - 1, 0));
        return true;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(filteredUsers[mentionIndex]);
        return true;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowMentions(false);
        return true;
      }
    }
    return false;
  }, [showMentions, filteredUsers, mentionIndex, insertMention]);

  const syncMentions = useCallback((newText) => {
    setMentionedUsers(prev => prev.filter(u => newText.includes(`@${u.name}`)));
  }, []);

  useEffect(() => {
    syncMentions(text);
  }, [text, syncMentions]);

  useEffect(() => {
    if (mentionListRef.current) {
      const active = mentionListRef.current.querySelector('[data-active="true"]');
      if (active) active.scrollIntoView({ block: 'nearest' });
    }
  }, [mentionIndex]);

  const reset = useCallback(() => {
    setText('');
    setMentionedUsers([]);
    setShowMentions(false);
  }, []);

  return {
    text, setText,
    showMentions, mentionSearch, mentionIndex, filteredUsers,
    mentionedUsers, setMentionedUsers,
    textareaRef, mentionListRef,
    cursorPos, setCursorPos,
    handleChange, handleKeyDown, insertMention,
    reset,
  };
}

export function CommentInput({ onSubmit, submitting, isMainAdmin, isAdmin, commentType, setCommentType, COMMENT_TYPE_CONFIG }) {
  const canMention = isAdmin || isMainAdmin;
  const externalUsers = useMentionableUsers(canMention);
  const {
    text, showMentions, mentionSearch, mentionIndex, filteredUsers,
    mentionedUsers,
    textareaRef, mentionListRef,
    setCursorPos,
    handleChange, handleKeyDown, insertMention,
    reset,
  } = useCommentMentions(externalUsers);

  const autoResize = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [textareaRef]);

  useEffect(() => { autoResize(); }, [text, autoResize]);

  const handleSubmit = () => {
    if (!text.trim() || submitting) return;
    const mentionIds = mentionedUsers.map(u => u.id);
    onSubmit(text, mentionIds);
    reset();
  };

  const onKeyDown = (e) => {
    if (handleKeyDown(e)) return;
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="space-y-3">
      {isMainAdmin && (
        <div className="flex gap-2">
          {Object.entries(COMMENT_TYPE_CONFIG).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => setCommentType(key)}
              className={`px-3 py-1 rounded-full text-[11px] font-medium border hub-btn ${
                commentType === key
                  ? `${cfg.bgColor} ${cfg.textColor} ${cfg.borderColor}`
                  : 'border-slate-200 text-muted-foreground hover:border-slate-300'
              }`}
            >
              {cfg.label}
            </button>
          ))}
        </div>
      )}

      <div className="relative">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleChange}
          onKeyDown={onKeyDown}
          onSelect={(e) => setCursorPos(e.target.selectionStart)}
          placeholder={canMention ? "اكتب تعليقك هنا... أو استخدم @ للإشارة إلى شخص" : "اكتب تعليقك هنا..."}
          className="w-full text-right min-h-[80px] max-h-[200px] p-3 pr-4 rounded-xl border border-slate-200 bg-white focus:border-brand-turquoise focus:ring-1 focus:ring-brand-turquoise/30 outline-none resize-none text-sm leading-relaxed hub-input-focus"
          rows={3}
          dir="rtl"
        />

        {showMentions && canMention && (
          <MentionDropdown
            users={filteredUsers}
            search={mentionSearch}
            activeIndex={mentionIndex}
            onSelect={insertMention}
            listRef={mentionListRef}
          />
        )}

        {mentionedUsers.length > 0 && (
          <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
            <AtSign className="h-3 w-3 text-brand-turquoise flex-shrink-0" />
            {mentionedUsers.map(u => (
              <span key={u.id} className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-brand-turquoise/10 text-brand-turquoise border border-brand-turquoise/20 font-medium">
                {u.name}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between mt-2">
          <span className="text-[10px] text-muted-foreground">
            Ctrl+Enter للإرسال{canMention ? ' • @ للإشارة' : ''}
          </span>
          <Button
            onClick={handleSubmit}
            disabled={!text.trim() || submitting}
            size="sm"
            className="bg-brand-navy hover:bg-brand-navy/90 text-white rounded-lg gap-1.5 h-9 px-4 hub-btn"
          >
            {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
            إرسال
          </Button>
        </div>
      </div>
    </div>
  );
}

function renderMentionContent(content, mentions = [], mentionableUsers = []) {
  if (!content) return null;

  const allKnown = [...(mentions || [])];
  (mentionableUsers || []).forEach(u => {
    if (!allKnown.find(m => m.id === u.id)) {
      allKnown.push({ id: u.id, name: u.name, email: u.email });
    }
  });

  if (allKnown.length === 0) return content;

  const sortedNames = allKnown
    .map(u => u.name)
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

  if (sortedNames.length === 0) return content;

  const escaped = sortedNames.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(@(?:${escaped.join('|')}))`, 'g');

  const parts = content.split(regex);
  return parts.map((part, i) => {
    if (part.startsWith('@')) {
      const nameOnly = part.slice(1);
      const user = allKnown.find(u => u.name === nameOnly);
      if (user) {
        return (
          <span
            key={i}
            className="inline-flex items-center bg-brand-turquoise/15 text-brand-turquoise font-medium px-1 py-0.5 rounded text-[13px] cursor-default hub-mention-token hover:bg-brand-turquoise/25 transition-colors duration-120"
            title={user.email || ''}
          >
            {part}
          </span>
        );
      }
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

export function CommentBubble({ comment, currentUserId, isMainAdmin, isAdmin, onEdit, onDelete, mentionableUsers = [] }) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(comment.content);
  const [editMentionedUsers, setEditMentionedUsers] = useState([]);
  const editRef = useRef(null);

  const canMention = isAdmin || isMainAdmin;
  const externalUsers = useMentionableUsers(canMention);
  const allMentionUsers = externalUsers.length > 0 ? externalUsers : mentionableUsers;

  const [showEditMentions, setShowEditMentions] = useState(false);
  const [editMentionSearch, setEditMentionSearch] = useState('');
  const [editMentionIndex, setEditMentionIndex] = useState(0);
  const [editCursorPos, setEditCursorPos] = useState(0);
  const editMentionListRef = useRef(null);

  const editFilteredUsers = allMentionUsers.filter(u => {
    if (!editMentionSearch) return true;
    const q = editMentionSearch.toLowerCase();
    return (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
  });

  const canEdit = false;
  const canDelete = false;

  const startEdit = () => {
    setEditing(true);
    setEditText(comment.content);
    const existingMentions = (comment.mentions || []).map(m => {
      if (typeof m === 'object') return m;
      const found = allMentionUsers.find(u => u.id === m);
      return found ? { id: found.id, name: found.name, email: found.email } : null;
    }).filter(Boolean);
    setEditMentionedUsers(existingMentions);
  };

  const handleEditChange = (e) => {
    const val = e.target.value;
    const pos = e.target.selectionStart;
    setEditText(val);
    setEditCursorPos(pos);

    const mention = getMentionAtPos(val, pos);
    if (mention !== null && canMention) {
      setEditMentionSearch(mention.search);
      setShowEditMentions(true);
      setEditMentionIndex(0);
    } else {
      setShowEditMentions(false);
    }

    setEditMentionedUsers(prev => prev.filter(u => val.includes(`@${u.name}`)));
  };

  const insertEditMention = (user) => {
    const mention = getMentionAtPos(editText, editCursorPos);
    if (!mention) return;
    const before = editText.slice(0, mention.start);
    const after = editText.slice(editCursorPos);
    const mentionText = `@${user.name} `;
    setEditText(before + mentionText + after);
    setShowEditMentions(false);
    setEditMentionedUsers(prev => {
      if (prev.find(m => m.id === user.id)) return prev;
      return [...prev, { id: user.id, name: user.name, email: user.email }];
    });
    requestAnimationFrame(() => {
      if (editRef.current) {
        const newPos = mention.start + mentionText.length;
        editRef.current.focus();
        editRef.current.setSelectionRange(newPos, newPos);
        setEditCursorPos(newPos);
      }
    });
  };

  const handleSaveEdit = () => {
    if (!editText.trim()) return;
    const mentionIds = editMentionedUsers.map(u => u.id);
    onEdit(comment.id, editText, mentionIds);
    setEditing(false);
  };

  const handleEditKeyDown = (e) => {
    if (showEditMentions && editFilteredUsers.length > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setEditMentionIndex(prev => Math.min(prev + 1, editFilteredUsers.length - 1)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setEditMentionIndex(prev => Math.max(prev - 1, 0)); return; }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); insertEditMention(editFilteredUsers[editMentionIndex]); return; }
      if (e.key === 'Escape') { e.preventDefault(); setShowEditMentions(false); return; }
    }
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); handleSaveEdit(); }
    if (e.key === 'Escape' && !showEditMentions) setEditing(false);
  };

  useEffect(() => {
    if (editing && editRef.current) {
      editRef.current.focus();
      editRef.current.style.height = 'auto';
      editRef.current.style.height = editRef.current.scrollHeight + 'px';
    }
  }, [editing]);

  useEffect(() => {
    if (editMentionListRef.current) {
      const active = editMentionListRef.current.querySelector('[data-active="true"]');
      if (active) active.scrollIntoView({ block: 'nearest' });
    }
  }, [editMentionIndex]);

  const commentMentions = (comment.mentions || []).map(m => {
    if (typeof m === 'object' && m.name) return m;
    const found = allMentionUsers.find(u => u.id === m);
    return found ? { id: found.id, name: found.name, email: found.email } : null;
  }).filter(Boolean);

  return (
    <div className="group relative">
      {editing ? (
        <div className="space-y-2 relative">
          <textarea
            ref={editRef}
            value={editText}
            onChange={handleEditChange}
            onKeyDown={handleEditKeyDown}
            onSelect={(e) => setEditCursorPos(e.target.selectionStart)}
            className="w-full text-right p-2.5 rounded-lg border border-brand-turquoise bg-white focus:ring-1 focus:ring-brand-turquoise/30 outline-none resize-none text-sm leading-relaxed"
            dir="rtl"
          />
          {showEditMentions && canMention && (
            <MentionDropdown
              users={editFilteredUsers}
              search={editMentionSearch}
              activeIndex={editMentionIndex}
              onSelect={insertEditMention}
              listRef={editMentionListRef}
            />
          )}
          {editMentionedUsers.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <AtSign className="h-3 w-3 text-brand-turquoise flex-shrink-0" />
              {editMentionedUsers.map(u => (
                <span key={u.id} className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-brand-turquoise/10 text-brand-turquoise border border-brand-turquoise/20 font-medium">
                  {u.name}
                </span>
              ))}
            </div>
          )}
          <div className="flex gap-2 justify-end">
            <Button size="sm" variant="ghost" className="h-7 text-xs gap-1" onClick={() => setEditing(false)}>
              <X className="h-3 w-3" />
              إلغاء
            </Button>
            <Button size="sm" className="h-7 text-xs bg-brand-navy text-white gap-1" onClick={handleSaveEdit} disabled={!editText.trim()}>
              <Check className="h-3 w-3" />
              حفظ
            </Button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-sm mt-1.5 leading-relaxed whitespace-pre-wrap">
            {renderMentionContent(comment.content, commentMentions, allMentionUsers)}
          </p>
          {comment.edited && (
            <span className="text-[9px] text-muted-foreground mt-0.5 inline-block">(تم التعديل)</span>
          )}
        </>
      )}

      {!editing && (canEdit || canDelete) && (
        <div className="absolute top-0 left-0 flex gap-1 hub-comment-actions">
          {canEdit && (
            <button
              onClick={startEdit}
              className="flex items-center gap-0.5 text-[10px] text-muted-foreground hover:text-brand-navy px-1.5 py-0.5 rounded bg-white/80 border border-slate-100 shadow-sm"
            >
              <Pencil className="h-2.5 w-2.5" />
              تعديل
            </button>
          )}
          {canDelete && (
            <button
              onClick={() => onDelete(comment.id)}
              className="flex items-center gap-0.5 text-[10px] text-red-400 hover:text-red-600 px-1.5 py-0.5 rounded bg-white/80 border border-slate-100 shadow-sm"
            >
              <Trash2 className="h-2.5 w-2.5" />
              حذف
            </button>
          )}
        </div>
      )}
    </div>
  );
}
