/**
 * TimetableVersionManager Component
 * إدارة نسخ الجدول
 * 
 * يعرض نسخ الجدول ويتيح التحكم بها
 */

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { 
  CheckCircle2, Clock, Archive, Eye, Send, 
  MoreVertical, Calendar, User, FileText, Sparkles,
  ChevronDown, ChevronUp
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import { TimetableStatus, getStatusBadgeStyle, getStatusLabel } from './types';

// Compact Version Item
const VersionItem = ({
  version,
  selected = false,
  onSelect,
  onPublish,
  onArchive
}) => {
  const statusStyle = getStatusBadgeStyle(version.status);
  const statusLabel = getStatusLabel(version.status);

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('ar-SA', {
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  const getStatusIcon = () => {
    switch (version.status) {
      case TimetableStatus.PUBLISHED:
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case TimetableStatus.DRAFT:
        return <Clock className="h-4 w-4 text-amber-600" />;
      default:
        return <Archive className="h-4 w-4 text-gray-500" />;
    }
  };

  return (
    <div 
      className={`p-3 rounded-lg border transition-all cursor-pointer ${
        selected 
          ? 'border-brand-navy bg-brand-navy/5' 
          : 'border-gray-200 hover:border-gray-300'
      }`}
      onClick={() => onSelect && onSelect(version.id)}
      data-testid={`version-item-${version.id}`}
    >
      <div className="flex items-center gap-3">
        {/* Status Icon */}
        <div className={`p-2 rounded-lg ${
          version.status === TimetableStatus.PUBLISHED 
            ? 'bg-green-100' 
            : version.status === TimetableStatus.DRAFT 
            ? 'bg-amber-100' 
            : 'bg-gray-100'
        }`}>
          {getStatusIcon()}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate">
              {version.versionName || `نسخة ${version.id?.substring(0, 6)}`}
            </span>
            <Badge className={`text-[10px] px-1.5 py-0 ${statusStyle}`}>
              {statusLabel.ar}
            </Badge>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
            {version.generatedAt && (
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {formatDate(version.generatedAt)}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Sparkles className="h-3 w-3" />
              {version.qualityScore || 0}%
            </span>
          </div>
        </div>

        {/* Actions */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
            <Button variant="ghost" size="icon" className="h-7 w-7">
              <MoreVertical className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onSelect && onSelect(version.id); }}>
              <Eye className="h-4 w-4 ml-2" />
              عرض
            </DropdownMenuItem>
            {version.status === TimetableStatus.DRAFT && onPublish && (
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onPublish(version.id); }}>
                <Send className="h-4 w-4 ml-2" />
                نشر
              </DropdownMenuItem>
            )}
            {version.status !== TimetableStatus.ARCHIVED && onArchive && (
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onArchive(version.id); }}>
                <Archive className="h-4 w-4 ml-2" />
                أرشفة
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
};

// Main Version Manager Component
const TimetableVersionManager = ({
  versions = [],
  selectedVersionId = null,
  loading = false,
  onSelectVersion,
  onPublishVersion,
  onArchiveVersion,
  onCompareVersion,
  onRestoreAsBase
}) => {
  const [showArchived, setShowArchived] = useState(false);

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <Skeleton className="h-5 w-28" />
        </CardHeader>
        <CardContent className="space-y-2">
          {[1, 2].map(i => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (versions.length === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-6 text-center">
          <FileText className="h-8 w-8 mx-auto text-muted-foreground/30 mb-2" />
          <p className="text-sm text-muted-foreground">لا توجد نسخ</p>
        </CardContent>
      </Card>
    );
  }

  // Group versions
  const publishedVersions = versions.filter(v => v.status === TimetableStatus.PUBLISHED);
  const draftVersions = versions.filter(v => v.status === TimetableStatus.DRAFT);
  const archivedVersions = versions.filter(v => v.status === TimetableStatus.ARCHIVED);

  return (
    <Card data-testid="timetable-version-manager">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="h-4 w-4 text-brand-navy" />
          نسخ الجدول
          <Badge variant="outline" className="text-xs">{versions.length}</Badge>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Published */}
        {publishedVersions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-green-700 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" />
              منشورة
            </p>
            {publishedVersions.map(version => (
              <VersionItem
                key={version.id}
                version={version}
                selected={selectedVersionId === version.id}
                onSelect={onSelectVersion}
                onArchive={onArchiveVersion}
              />
            ))}
          </div>
        )}

        {/* Drafts */}
        {draftVersions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-amber-700 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              مسودات ({draftVersions.length})
            </p>
            {draftVersions.slice(0, 3).map(version => (
              <VersionItem
                key={version.id}
                version={version}
                selected={selectedVersionId === version.id}
                onSelect={onSelectVersion}
                onPublish={onPublishVersion}
                onArchive={onArchiveVersion}
              />
            ))}
            {draftVersions.length > 3 && (
              <p className="text-xs text-muted-foreground text-center">
                +{draftVersions.length - 3} مسودة أخرى
              </p>
            )}
          </div>
        )}

        {/* Archived - Collapsible */}
        {archivedVersions.length > 0 && (
          <div className="space-y-2">
            <button
              onClick={() => setShowArchived(!showArchived)}
              className="w-full flex items-center justify-between text-xs font-medium text-gray-500 hover:text-gray-700 py-1"
            >
              <span className="flex items-center gap-1">
                <Archive className="h-3 w-3" />
                الأرشيف ({archivedVersions.length})
              </span>
              {showArchived ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>
            
            {showArchived && (
              <div className="space-y-2 opacity-70">
                {archivedVersions.slice(0, 5).map(version => (
                  <VersionItem
                    key={version.id}
                    version={version}
                    selected={selectedVersionId === version.id}
                    onSelect={onSelectVersion}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TimetableVersionManager;
export { VersionItem };
