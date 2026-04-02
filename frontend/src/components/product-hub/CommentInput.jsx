import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '../ui/button';
import { Avatar, AvatarFallback } from '../ui/avatar';
import { Send, Loader2, AtSign } from 'lucide-react';
import axios from 'axios';

const authHeaders = () => {
  const t = localStorage.getItem('nassaq_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

export function CommentInput({ onSubmit, submitting, isMainAdmin, commentType, setCommentType, COMMENT_TYPE_CONFIG }) {
  const [text, setText] = useState('');
  const [mentionableUsers, setMentionableUsers] = useState([]);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionSearch, setMentionSearch] = useState('');
  const [mentionIndex, setMentionIndex] = useState(0);
  const [cursorPos, setCursorPos] = useState(0);
  const textareaRef = useRef(null);
  const mentionListRef = useRef(null);
  const [mentionedIds, setMentionedIds] = useState([]);

  useEffect(() => {
    if (isMainAdmin) {
      axios.get('/api/product-hub/mentionable-users', { headers: authHeaders() })
        .then(res => setMentionableUsers(res.data.users || []))
        .catch(() => {});
    }
  }, [isMainAdmin]);

  const filteredUsers = mentionableUsers.filter(u => {
    if (!mentionSearch) return true;
    const q = mentionSearch.toLowerCase();
    return (u.name || '').toLowerCase().includes(q) || (u.email || '').toLowerCase().includes(q);
  });

  const getMentionStartPos = useCallback(() => {
    const before = text.slice(0, cursorPos);
    const atIdx = before.lastIndexOf('@');
    if (atIdx === -1) return -1;
    const textBetween = before.slice(atIdx + 1);
    if (textBetween.includes(' ') && textBetween.includes('\n')) return -1;
    return atIdx;
  }, [text, cursorPos]);

  const handleChange = (e) => {
    const val = e.target.value;
    const pos = e.target.selectionStart;
    setText(val);
    setCursorPos(pos);

    const before = val.slice(0, pos);
    const atIdx = before.lastIndexOf('@');
    if (atIdx !== -1) {
      const afterAt = before.slice(atIdx + 1);
      if (!afterAt.includes('\n') && afterAt.length < 30) {
        setMentionSearch(afterAt);
        setShowMentions(true);
        setMentionIndex(0);
        return;
      }
    }
    setShowMentions(false);
  };

  const insertMention = (user) => {
    const atPos = getMentionStartPos();
    if (atPos === -1) return;
    const before = text.slice(0, atPos);
    const after = text.slice(cursorPos);
    const mentionText = `@${user.name} `;
    const newText = before + mentionText + after;
    setText(newText);
    setShowMentions(false);
    setMentionedIds(prev => [...new Set([...prev, user.id])]);

    requestAnimationFrame(() => {
      if (textareaRef.current) {
        const newPos = atPos + mentionText.length;
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newPos, newPos);
        setCursorPos(newPos);
      }
    });
  };

  const handleKeyDown = (e) => {
    if (showMentions && filteredUsers.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex(prev => Math.min(prev + 1, filteredUsers.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex(prev => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(filteredUsers[mentionIndex]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowMentions(false);
        return;
      }
    }

    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!text.trim() || submitting) return;
    onSubmit(text, mentionedIds);
    setText('');
    setMentionedIds([]);
  };

  useEffect(() => {
    if (mentionListRef.current) {
      const active = mentionListRef.current.querySelector('[data-active="true"]');
      if (active) active.scrollIntoView({ block: 'nearest' });
    }
  }, [mentionIndex]);

  const autoResize = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, []);

  useEffect(() => { autoResize(); }, [text, autoResize]);

  return (
    <div className="space-y-3">
      {isMainAdmin && (
        <div className="flex gap-2">
          {Object.entries(COMMENT_TYPE_CONFIG).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => setCommentType(key)}
              className={`px-3 py-1 rounded-full text-[11px] font-medium border transition-all ${
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
          onKeyDown={handleKeyDown}
          onSelect={(e) => setCursorPos(e.target.selectionStart)}
          placeholder="اكتب تعليقك هنا... أو استخدم @ للإشارة إلى شخص"
          className="w-full text-right min-h-[80px] max-h-[200px] p-3 pr-4 rounded-xl border border-slate-200 bg-white focus:border-brand-turquoise focus:ring-1 focus:ring-brand-turquoise/30 outline-none resize-none text-sm leading-relaxed transition-all"
          rows={3}
          dir="rtl"
        />

        {showMentions && filteredUsers.length > 0 && (
          <div
            ref={mentionListRef}
            className="absolute z-50 bottom-full mb-1 right-0 w-72 max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-lg"
          >
            <div className="p-2 border-b border-slate-100 flex items-center gap-1.5">
              <AtSign className="h-3 w-3 text-brand-turquoise" />
              <span className="text-[10px] text-muted-foreground">إشارة إلى مستخدم</span>
            </div>
            {filteredUsers.map((u, i) => (
              <button
                key={u.id}
                data-active={i === mentionIndex}
                onMouseDown={(e) => { e.preventDefault(); insertMention(u); }}
                className={`w-full flex items-center gap-2.5 p-2.5 text-right transition-colors ${
                  i === mentionIndex ? 'bg-brand-turquoise/10' : 'hover:bg-slate-50'
                }`}
              >
                <Avatar className="h-7 w-7 flex-shrink-0">
                  <AvatarFallback className="bg-brand-navy text-white text-[10px]">
                    {(u.name || '?')[0]}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0 text-right">
                  <p className="text-xs font-semibold text-foreground truncate">{u.name}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{u.email}</p>
                </div>
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between mt-2">
          <span className="text-[10px] text-muted-foreground">
            Ctrl+Enter للإرسال • @ للإشارة
          </span>
          <Button
            onClick={handleSubmit}
            disabled={!text.trim() || submitting}
            size="sm"
            className="bg-brand-navy hover:bg-brand-navy/90 text-white rounded-lg gap-1.5 h-9 px-4"
          >
            {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
            إرسال
          </Button>
        </div>
      </div>
    </div>
  );
}

export function CommentBubble({ comment, currentUserId, isMainAdmin, onEdit, onDelete, mentionableUsers = [] }) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(comment.content);
  const editRef = useRef(null);

  const isOwner = comment.user_id === currentUserId || comment.created_by === currentUserId;
  const canEdit = isOwner;
  const canDelete = isOwner || isMainAdmin;

  const handleSaveEdit = () => {
    if (!editText.trim()) return;
    onEdit(comment.id, editText);
    setEditing(false);
  };

  useEffect(() => {
    if (editing && editRef.current) {
      editRef.current.focus();
      editRef.current.style.height = 'auto';
      editRef.current.style.height = editRef.current.scrollHeight + 'px';
    }
  }, [editing]);

  const renderContent = (content) => {
    if (!content) return null;
    const parts = content.split(/(@[\u0600-\u06FFa-zA-Z\s]+?)(?=\s|@|$)/g);
    return parts.map((part, i) => {
      if (part.startsWith('@')) {
        const nameMatch = mentionableUsers.find(u => part.includes(u.name));
        if (nameMatch) {
          return <span key={i} className="bg-brand-turquoise/15 text-brand-turquoise font-medium px-0.5 rounded">{part}</span>;
        }
      }
      return <React.Fragment key={i}>{part}</React.Fragment>;
    });
  };

  return (
    <div className="group relative">
      {editing ? (
        <div className="space-y-2">
          <textarea
            ref={editRef}
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); handleSaveEdit(); }
              if (e.key === 'Escape') setEditing(false);
            }}
            className="w-full text-right p-2.5 rounded-lg border border-brand-turquoise bg-white focus:ring-1 focus:ring-brand-turquoise/30 outline-none resize-none text-sm leading-relaxed"
            dir="rtl"
          />
          <div className="flex gap-2 justify-end">
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditing(false)}>إلغاء</Button>
            <Button size="sm" className="h-7 text-xs bg-brand-navy text-white" onClick={handleSaveEdit} disabled={!editText.trim()}>حفظ</Button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-sm mt-1.5 leading-relaxed whitespace-pre-wrap">{renderContent(comment.content)}</p>
          {comment.edited && (
            <span className="text-[9px] text-muted-foreground mt-0.5 inline-block">(تم التعديل)</span>
          )}
        </>
      )}

      {!editing && (canEdit || canDelete) && (
        <div className="absolute top-0 left-0 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
          {canEdit && (
            <button
              onClick={() => { setEditing(true); setEditText(comment.content); }}
              className="text-[10px] text-muted-foreground hover:text-brand-navy px-1.5 py-0.5 rounded bg-white/80 border border-slate-100 shadow-sm"
            >
              تعديل
            </button>
          )}
          {canDelete && (
            <button
              onClick={() => onDelete(comment.id)}
              className="text-[10px] text-red-400 hover:text-red-600 px-1.5 py-0.5 rounded bg-white/80 border border-slate-100 shadow-sm"
            >
              حذف
            </button>
          )}
        </div>
      )}
    </div>
  );
}
