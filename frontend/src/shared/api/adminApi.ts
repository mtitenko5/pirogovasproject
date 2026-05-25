import { apiClient } from './apiClient';
import type {
  User,
  UserFormValues,
  UserRole,
} from '../../entities/user/model/types';

type BackendUser = {
  id: number;
  login: string;
  role: UserRole;
  organization_name: string;
  name: string;
  surname: string;
  patronymic?: string | null;
  date_of_birth: string;
  is_active: boolean;
};

export type AdminMetrics = {
  llm_calls_total: number;
  llm_calls_failed: number;
  llm_error_percent: number;
  reviewed_reports_total: number;
  average_review_score: number | null;
};

export type ReportTemplate = {
  id: number;
  name: string;
  version: string;
  description?: string | null;
  is_active: boolean;
  created_by_user_id: number;
  created_at: string;
  updated_at: string;
};

const toIsoDate = (value: string) => {
  const match = value.trim().match(/^(\d{2})\.(\d{2})\.(\d{4})$/);

  return match ? `${match[3]}-${match[2]}-${match[1]}` : value;
};

const mapUser = (user: BackendUser): User => ({
  id: String(user.id),
  fullName: [user.surname, user.name, user.patronymic]
    .filter(Boolean)
    .join(' '),
  lastName: user.surname,
  firstName: user.name,
  middleName: user.patronymic ?? '',
  birthDate: user.date_of_birth,
  login: user.login,
  organization: user.organization_name,
  role: user.role,
  status: user.is_active ? 'active' : 'inactive',
});

export const getAdminUsers = async (): Promise<User[]> => {
  const users = await apiClient<BackendUser[]>('/admin/users');

  return users.map(mapUser);
};

export const createAdminUser = async (
  values: UserFormValues
): Promise<User> => {
  const user = await apiClient<BackendUser>('/admin/create_user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      login: values.login,
      password: values.password,
      role: values.role,
      organization_name: values.organization,
      name: values.firstName,
      surname: values.lastName,
      patronymic: values.middleName || null,
      date_of_birth: toIsoDate(values.birthDate),
    }),
  });

  return mapUser(user);
};

export const updateAdminUser = async (
  userId: string,
  values: UserFormValues
): Promise<User> => {
  const user = await apiClient<BackendUser>(`/admin/update_user/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      role: values.role,
      organization_name: values.organization,
      name: values.firstName,
      surname: values.lastName,
      patronymic: values.middleName || null,
      date_of_birth: toIsoDate(values.birthDate),
    }),
  });

  return mapUser(user);
};

export const getAdminMetrics = () => {
  return apiClient<AdminMetrics>('/admin/metrics');
};

export const getReportTemplates = () => {
  return apiClient<ReportTemplate[]>('/admin/report-templates');
};

export const uploadReportTemplate = (
  file: File,
  name: string,
  version: string,
  isActive = false
) => {
  const formData = new FormData();

  formData.append('name', name);
  formData.append('version', version);
  formData.append('template_file', file);
  formData.append('is_active', String(isActive));

  return apiClient<ReportTemplate>('/admin/report-templates/upload', {
    method: 'POST',
    body: formData,
  });
};

export type ClinicalProtocolListItem = {
  id: number;
  title: string;
  status: string;
  uploaded_at: string;
};

export const getClinicalProtocols = () => {
  return apiClient<ClinicalProtocolListItem[]>('/admin/clinical-protocols');
};

export const uploadClinicalProtocol = async (file: File): Promise<void> => {
  const formData = new FormData();

  formData.append('file', file);

  await apiClient<unknown>('/admin/clinical-protocols/add', {
    method: 'POST',
    body: formData,
  });
};