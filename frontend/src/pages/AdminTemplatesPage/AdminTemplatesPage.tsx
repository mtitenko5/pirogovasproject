import { useEffect, useState } from 'react';
import { FileInput } from '../../shared/ui/FileInput/FileInput';
import { Button } from '../../shared/ui/Button/Button';
import {
  getReportTemplates,
  uploadReportTemplate,
} from '../../shared/api/adminApi';
import downloadIcon from '../../shared/assets/icons/downloadIcon.svg';
import cls from './AdminTemplatesPage.module.scss';

type TemplateVersion = {
  id: string;
  version: string;
  status: 'active' | 'inactive';
  date: string;
};

const getCurrentDate = () => {
  return new Date().toLocaleDateString('ru-RU');
};

export const AdminTemplatesPage = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [versions, setVersions] = useState<TemplateVersion[]>([]);

  useEffect(() => {
    getReportTemplates()
      .then((templates) => {
        setVersions(
          templates.map((template) => ({
            id: String(template.id),
            version: `${template.name} ${template.version}`,
            status: template.is_active ? 'active' : 'inactive',
            date: new Date(template.created_at).toLocaleDateString('ru-RU'),
          }))
        );
      })
      .catch(console.error);
  }, []);

  const handleUpload = async () => {
    if (files.length === 0) {
      console.log('Файл шаблона не выбран');
      return;
    }

    const file = files[0];
    const template = await uploadReportTemplate(
      file,
      file.name,
      getCurrentDate(),
      true
    );

    setVersions((prevVersions) => [
      {
        id: String(template.id),
        version: `${template.name} ${template.version}`,
        status: template.is_active ? 'active' : 'inactive',
        date: new Date(template.created_at).toLocaleDateString('ru-RU'),
      },
      ...prevVersions,
    ]);
    setFiles([]);
  };

  return (
    <div className={cls.page}>
      <section className={cls.uploadSection}>
        <h1 className={cls.title}>Загрузка нового шаблона</h1>

        <FileInput
          files={files}
          onChange={setFiles}
          allowedExtensions={['html']}
          multiple={false}
          placeholder="Выберите файл (.html)"
        />

        <Button
          type="button"
          className={cls.uploadButton}
          onClick={handleUpload}
        >
          Загрузить
        </Button>
      </section>

      <section className={cls.historySection}>
        <h2 className={cls.subtitle}>История версий</h2>

        <table className={cls.table}>
          <thead>
            <tr>
              <th>Версия</th>
              <th>Статус</th>
              <th>Дата</th>
              <th>Действия</th>
            </tr>
          </thead>

          <tbody>
            {versions.map((version) => (
              <tr key={version.id}>
                <td>{version.version}</td>
                <td>{version.status}</td>
                <td>{version.date}</td>
                <td>
                  <button
                    type="button"
                    className={cls.iconButton}
                    aria-label="Скачать шаблон"
                  >
                    <img src={downloadIcon} alt="" className={cls.downloadIcon}/>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
};
