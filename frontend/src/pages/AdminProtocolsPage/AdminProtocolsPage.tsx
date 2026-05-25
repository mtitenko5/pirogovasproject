import { useCallback, useEffect, useMemo, useState } from 'react';
import { SearchBar } from '../../shared/ui/SearchBar/SearchBar';
import { FileInput } from '../../shared/ui/FileInput/FileInput';
import { Button } from '../../shared/ui/Button/Button';
import {getClinicalProtocols, uploadClinicalProtocol, type ClinicalProtocolListItem,} from '../../shared/api/adminApi';
import fileIcon from '../../shared/assets/icons/fileBlueIcon.svg';
import cls from './AdminProtocolsPage.module.scss';

export const AdminProtocolsPage = () => {
  const [searchValue, setSearchValue] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [protocols, setProtocols] = useState<ClinicalProtocolListItem[]>([]);

  const loadProtocols = useCallback(async () => {
    try {
      const data = await getClinicalProtocols();
      setProtocols(data);
    } catch {
      console.log('Не удалось загрузить клинические рекомендации');
    }
  }, []);

  useEffect(() => {
    loadProtocols();
  }, [loadProtocols]);

  const filteredProtocols = useMemo(() => {
    const normalizedSearch = searchValue.trim().toLowerCase();

    if (!normalizedSearch) {
      return protocols;
    }

    return protocols.filter((protocol) =>
      protocol.title.toLowerCase().includes(normalizedSearch)
    );
  }, [searchValue, protocols]);

  const handleSearchSubmit = () => {
    console.log('Поиск протокола:', searchValue);
  };

  const handleUpload = async () => {
    const file = files[0];

    if (!file) {
      console.log('Файл протокола не выбран');
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      console.log('Можно загрузить только PDF-файл');
      return;
    }

    try {
      await uploadClinicalProtocol(file);

      setFiles([]);
      await loadProtocols();
    } catch {
      console.log('Не удалось загрузить клинический протокол');
    }
  };

  return (
    <div className={cls.page}>
      <SearchBar
        value={searchValue}
        onChange={setSearchValue}
        onSearch={handleSearchSubmit}
        placeholder="Поиск..."
      />

      <section className={cls.uploadSection}>
        <h1 className={cls.title}>Загрузка нового протокола</h1>

        <FileInput
          files={files}
          onChange={setFiles}
          allowedExtensions={['pdf']}
          placeholder="Выберите файл (pdf)"
        />

        <Button
          type="button"
          className={cls.uploadButton}
          onClick={handleUpload}
        >
          Загрузить
        </Button>
      </section>

      <section className={cls.currentSection}>
        <h2 className={cls.subtitle}>Текущие клинические рекомендации</h2>

        <ul className={cls.fileList}>
          {filteredProtocols.map((protocol) => (
            <li key={protocol.id} className={cls.fileItem}>
              <img src={fileIcon} alt="" className={cls.protocolIcon} />
              <span>{protocol.title}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
};