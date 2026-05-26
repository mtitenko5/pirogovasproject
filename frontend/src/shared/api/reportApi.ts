import { apiClient } from './apiClient';
import { tokenStorage } from '../lib/tokenStorage';
import type { Report } from '../../entities/report/model/types';

const API_URL = import.meta.env.VITE_API_URL;

interface CreateReportPayload {
  patientName: string;
  gender: string;
  birthDate: string;
  ctDate: string;
  anamnesis: string;
  ctImages: File[];
  measurementsFile: File;
}

interface CreateReportResponse {
  id_report: string;
  status: Report['status'];
}

interface BackendReport {
  id_report: string;
  status: Report['status'];
  error_message?: string | null;
  html_ready?: boolean;
  pdf_ready?: boolean;
  review_score?: number | null;
  review_text?: string | null;
  meta?: {
    name?: string;
    ct_date?: string;
    birth_date?: string;
    sex?: string;
    anamnesis?: string;
  };
}

interface ReportsListResponse {
  reports: BackendReport[];
}

const toIsoDate = (value: string): string => {
  const trimmed = value.trim();

  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return trimmed;
  }

  const match = trimmed.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);

  if (!match) {
    return trimmed;
  }

  const [, day, month, year] = match;

  return `${year}-${month}-${day}`;
};

const mapReport = (report: BackendReport): Report => {
  return {
    id: report.id_report,
    patientName: report.meta?.name ?? 'Без имени',
    studyDate: report.meta?.ct_date ?? '—',
    status: report.status,
    htmlReady: report.html_ready,
    pdfReady: report.pdf_ready,
    errorMessage: report.error_message ?? null,
    reviewScore: report.review_score ?? null,
    reviewText: report.review_text ?? null,
  };
};

export const createReport = async (
  payload: CreateReportPayload
): Promise<Report> => {
  const formData = new FormData();

  formData.append('patient_name', payload.patientName);
  formData.append('patient_sex', payload.gender);
  formData.append('birth_date', toIsoDate(payload.birthDate));
  formData.append('ct_date', toIsoDate(payload.ctDate));
  formData.append('medical_text', payload.anamnesis);
  formData.append('enable_llm_judge', 'false');

  payload.ctImages.forEach((file) => {
    formData.append('ct_images', file);
  });
  formData.append('measurements_file', payload.measurementsFile);

  const data = await apiClient<CreateReportResponse>('/llm/create_report', {
    method: 'POST',
    body: formData,
  });

  return {
    id: data.id_report,
    patientName: payload.patientName,
    studyDate: payload.ctDate,
    status: data.status,
  };
};

export const getMyReports = async (): Promise<Report[]> => {
  const data = await apiClient<ReportsListResponse>('/reports/my_reports');

  return data.reports.map(mapReport);
};

export const getReportStatus = async (reportId: string): Promise<Report> => {
  const data = await apiClient<BackendReport>(`/reports/${reportId}/status`);

  return mapReport(data);
};

export const viewHtmlReport = async (reportId: string) => {
  const token = tokenStorage.getToken();

  const response = await fetch(`${API_URL}/reports/${reportId}/view_html`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error('Не удалось открыть HTML-отчёт');
  }

  const html = await response.text();
  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);

  window.open(url, '_blank');

  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 60_000);
};

export const openPdfReport = async (reportId: string) => {
  const token = tokenStorage.getToken();

  const response = await fetch(`${API_URL}/reports/${reportId}/pdf`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error('Не удалось скачать PDF-отчет');
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');

  link.href = url;
  link.download = `report-${reportId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(url);
};
interface AddReportReviewPayload {
  review_score: number;
  review_text?: string;
}

export const addReportReview = async (
  reportId: string,
  rating: number,
  comment: string
): Promise<void> => {
  const payload: AddReportReviewPayload = {
    review_score: rating,
    review_text: comment.trim() || undefined,
  };

  await apiClient(`/reports/${reportId}/add_review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
};
