export type ReportStatus = 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'processing' | 'completed' | 'failed';

export interface Report {
  id: string;
  patientName: string;
  studyDate: string;
  status: ReportStatus;
  htmlReady?: boolean;
  pdfReady?: boolean;
  errorMessage?: string | null;
  reviewScore?: number | null;
  reviewText?: string | null;
}
