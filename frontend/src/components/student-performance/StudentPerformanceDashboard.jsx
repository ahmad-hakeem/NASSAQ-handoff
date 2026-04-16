import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import ExecutiveSummaryCards from './ExecutiveSummaryCards';
import StudentRiskMap from './StudentRiskMap';
import InterventionList from './InterventionList';
import RootCauseChart from './RootCauseChart';
import HakimRecommendations from './HakimRecommendations';
import InterventionActionModal from './InterventionActionModal';

export default function StudentPerformanceDashboard() {
  const { t } = useTranslation();
  const { api } = useAuth();
  const [data, setData] = useState(null);
  const [recs, setRecs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modal, setModal] = useState(null);

  const load = useCallback(async (force = false) => {
    const qs = force ? '?refresh=1' : '';
    setRefreshing(force);
    try {
      const [ov, rc] = await Promise.all([
        api.get(`/ai/insights/students-overview${qs}`),
        api.get('/ai/insights/recommendations-ai').catch(() => ({ data: { recommendations: [], source: 'fallback' } })),
      ]);
      setData(ov.data);
      setRecs(rc.data);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api]);

  useEffect(() => { load(false); }, [load]);

  if (loading || !data) {
    return <div className="p-6 text-center text-neutral-500">{t('loading')}</div>;
  }

  return (
    <div dir="rtl" className="space-y-6 font-tajawal">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-cairo text-[#1C3D74]">{t('studentPerformance')}</h2>
        <Button variant="outline" onClick={() => load(true)} disabled={refreshing}>
          <RefreshCw className={`ms-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          {t('refreshData')}
        </Button>
      </div>

      <ExecutiveSummaryCards summary={data.summary} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <StudentRiskMap points={data.risk_map} />
        <InterventionList
          items={data.intervention_list}
          onAction={(student, actionType) => setModal({ student, actionType })}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RootCauseChart causes={data.root_causes} />
        <HakimRecommendations
          recommendations={recs?.recommendations || []}
          source={recs?.source}
        />
      </div>

      {modal && (
        <InterventionActionModal
          student={modal.student}
          actionType={modal.actionType}
          onClose={() => setModal(null)}
          onSuccess={() => { setModal(null); load(true); }}
        />
      )}
    </div>
  );
}
