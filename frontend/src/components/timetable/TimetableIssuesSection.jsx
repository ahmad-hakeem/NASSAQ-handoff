/**
 * TimetableIssuesSection Component
 * قسم المشاكل والتحذيرات
 * 
 * يعرض قائمة المشاكل والتحذيرات المرتبطة بالنسخة الحالية
 */

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { 
  AlertTriangle, XCircle, Info, ChevronDown, ChevronUp,
  ArrowUpRight, CheckCircle2, AlertCircle, Filter
} from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../../components/ui/accordion';
import { IssueSeverity, IssueType } from './types';

// Issue Severity Badge Component
const IssueSeverityBadge = ({ severity }) => {
  const getConfig = () => {
    switch (severity) {
      case IssueSeverity.CRITICAL:
        return { label: 'حرج', className: 'bg-red-100 text-red-700 border-red-200' };
      case IssueSeverity.HIGH:
        return { label: 'عالي', className: 'bg-orange-100 text-orange-700 border-orange-200' };
      case IssueSeverity.MEDIUM:
        return { label: 'متوسط', className: 'bg-amber-100 text-amber-700 border-amber-200' };
      case IssueSeverity.LOW:
        return { label: 'منخفض', className: 'bg-blue-100 text-blue-700 border-blue-200' };
      default:
        return { label: severity, className: 'bg-gray-100 text-gray-700 border-gray-200' };
    }
  };

  const config = getConfig();

  return (
    <Badge variant="outline" className={`text-xs ${config.className}`}>
      {config.label}
    </Badge>
  );
};

// Issue Accordion Item Component
const IssueAccordionItem = ({ issue, onFix, onView }) => {
  const getIcon = () => {
    switch (issue.severity || issue.type) {
      case IssueSeverity.CRITICAL:
      case IssueType.CRITICAL:
        return <XCircle className="h-4 w-4 text-red-500" />;
      case IssueSeverity.HIGH:
      case IssueSeverity.MEDIUM:
      case IssueType.WARNING:
        return <AlertTriangle className="h-4 w-4 text-amber-500" />;
      default:
        return <Info className="h-4 w-4 text-blue-500" />;
    }
  };

  const getBg = () => {
    switch (issue.severity || issue.type) {
      case IssueSeverity.CRITICAL:
      case IssueType.CRITICAL:
        return 'hover:bg-red-50/50';
      case IssueSeverity.HIGH:
      case IssueSeverity.MEDIUM:
      case IssueType.WARNING:
        return 'hover:bg-amber-50/50';
      default:
        return 'hover:bg-blue-50/50';
    }
  };

  return (
    <AccordionItem value={issue.id} className="border rounded-lg px-3 mb-2">
      <AccordionTrigger className={`py-3 ${getBg()} rounded transition-colors [&[data-state=open]]:rounded-b-none`}>
        <div className="flex items-center gap-3 text-right w-full">
          {getIcon()}
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm truncate">{issue.title}</p>
            <p className="text-xs text-muted-foreground truncate">
              {issue.relatedEntityType && issue.relatedEntityName && (
                <span>{issue.relatedEntityType}: {issue.relatedEntityName}</span>
              )}
            </p>
          </div>
          <IssueSeverityBadge severity={issue.severity || issue.type} />
        </div>
      </AccordionTrigger>
      <AccordionContent className="pb-3">
        <div className="space-y-3 pr-7">
          <p className="text-sm text-muted-foreground">{issue.description}</p>
          
          {issue.recommendedAction && (
            <div className="p-2 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-xs text-blue-700">
                <span className="font-medium">الإجراء المقترح:</span> {issue.recommendedAction}
              </p>
            </div>
          )}

          <div className="flex items-center gap-2">
            {onFix && issue.fixRoute && (
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => onFix(issue.id, issue.fixRoute)}
                className="gap-1"
              >
                إصلاح
                <ArrowUpRight className="h-3 w-3" />
              </Button>
            )}
            {onView && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => onView(issue.id)}
              >
                عرض التفاصيل
              </Button>
            )}
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
};

// Main Issues Section Component
const TimetableIssuesSection = ({
  items = [],
  loading = false,
  onOpenIssue,
  onFixIssue
}) => {
  const [filterSeverity, setFilterSeverity] = useState(null);
  const [expanded, setExpanded] = useState(true);

  if (loading) {
    return (
      <Card className="border-2 border-gray-200">
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent className="space-y-3">
          {[1, 2, 3].map(i => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  // Group issues by severity
  const criticalIssues = items.filter(
    i => i.severity === IssueSeverity.CRITICAL || i.type === IssueType.CRITICAL
  );
  const highIssues = items.filter(i => i.severity === IssueSeverity.HIGH);
  const mediumIssues = items.filter(
    i => i.severity === IssueSeverity.MEDIUM || i.type === IssueType.WARNING
  );
  const lowIssues = items.filter(
    i => i.severity === IssueSeverity.LOW || i.type === IssueType.INFO
  );

  // Filter items if filter is applied
  const filteredItems = filterSeverity 
    ? items.filter(i => i.severity === filterSeverity || i.type === filterSeverity)
    : items;

  if (items.length === 0) {
    return (
      <Card className="border-2 border-green-200 bg-green-50/50">
        <CardContent className="py-8 text-center">
          <CheckCircle2 className="h-12 w-12 mx-auto text-green-500 mb-4" />
          <p className="font-medium text-green-700">لا توجد مشاكل أو تحذيرات</p>
          <p className="text-xs text-green-600 mt-1">الجدول الحالي سليم</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-2 border-amber-200/50" data-testid="timetable-issues-section">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <AlertCircle className="h-5 w-5 text-amber-600" />
              المشاكل والتحذيرات
            </CardTitle>
            <Badge variant="outline" className="text-amber-600 border-amber-300">
              {items.length}
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            {/* Severity Filter */}
            <div className="flex items-center gap-1">
              {criticalIssues.length > 0 && (
                <Button
                  variant={filterSeverity === IssueSeverity.CRITICAL ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 gap-1 text-xs"
                  onClick={() => setFilterSeverity(
                    filterSeverity === IssueSeverity.CRITICAL ? null : IssueSeverity.CRITICAL
                  )}
                >
                  <XCircle className="h-3 w-3" />
                  {criticalIssues.length}
                </Button>
              )}
              {(highIssues.length > 0 || mediumIssues.length > 0) && (
                <Button
                  variant={filterSeverity === IssueSeverity.MEDIUM ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 gap-1 text-xs"
                  onClick={() => setFilterSeverity(
                    filterSeverity === IssueSeverity.MEDIUM ? null : IssueSeverity.MEDIUM
                  )}
                >
                  <AlertTriangle className="h-3 w-3" />
                  {highIssues.length + mediumIssues.length}
                </Button>
              )}
              {lowIssues.length > 0 && (
                <Button
                  variant={filterSeverity === IssueSeverity.LOW ? 'default' : 'outline'}
                  size="sm"
                  className="h-7 gap-1 text-xs"
                  onClick={() => setFilterSeverity(
                    filterSeverity === IssueSeverity.LOW ? null : IssueSeverity.LOW
                  )}
                >
                  <Info className="h-3 w-3" />
                  {lowIssues.length}
                </Button>
              )}
            </div>

            {/* Expand/Collapse */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExpanded(!expanded)}
              className="gap-1"
            >
              {expanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent>
          {/* Summary Badges */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {criticalIssues.length > 0 && (
              <Badge className="bg-red-100 text-red-700 border-red-200 gap-1">
                <XCircle className="h-3 w-3" />
                {criticalIssues.length} حرج
              </Badge>
            )}
            {highIssues.length > 0 && (
              <Badge className="bg-orange-100 text-orange-700 border-orange-200 gap-1">
                <AlertTriangle className="h-3 w-3" />
                {highIssues.length} عالي
              </Badge>
            )}
            {mediumIssues.length > 0 && (
              <Badge className="bg-amber-100 text-amber-700 border-amber-200 gap-1">
                <AlertTriangle className="h-3 w-3" />
                {mediumIssues.length} متوسط
              </Badge>
            )}
            {lowIssues.length > 0 && (
              <Badge className="bg-blue-100 text-blue-700 border-blue-200 gap-1">
                <Info className="h-3 w-3" />
                {lowIssues.length} منخفض
              </Badge>
            )}
          </div>

          {/* Issues Accordion */}
          <Accordion type="single" collapsible className="w-full">
            {filteredItems.map(issue => (
              <IssueAccordionItem
                key={issue.id}
                issue={issue}
                onFix={onFixIssue}
                onView={onOpenIssue}
              />
            ))}
          </Accordion>
        </CardContent>
      )}
    </Card>
  );
};

export default TimetableIssuesSection;
export { IssueAccordionItem, IssueSeverityBadge };
