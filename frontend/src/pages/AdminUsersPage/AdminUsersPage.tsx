import { useEffect, useMemo, useState } from 'react';
import type { User, UserFormValues } from '../../entities/user/model/types';
import { AdminUsersToolbar } from '../../widgets/AdminUsersToolbar/AdminUsersToolbar';
import { UsersTable } from '../../widgets/UsersTable/UsersTable';
import { UserFormModal } from '../../features/user-form-modal/UserFormModal';
import { UserInfoModal } from '../../features/view-user-modal/UserInfoModal';
import {
  createAdminUser,
  getAdminUsers,
  updateAdminUser,
} from '../../shared/api/adminApi';
import addIcon from '../../shared/assets/icons/addIcon.svg';
import cls from './AdminUsersPage.module.scss';

export const AdminUsersPage = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [searchValue, setSearchValue] = useState('');
  const [loadError, setLoadError] = useState('');

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [viewUser, setViewUser] = useState<User | null>(null);
  const [editUser, setEditUser] = useState<User | null>(null);

  useEffect(() => {
    getAdminUsers()
      .then(setUsers)
      .catch((error) => {
        setLoadError(
          error instanceof Error ? error.message : 'Не удалось загрузить пользователей'
        );
      });
  }, []);

  const filteredUsers = useMemo(() => {
    const normalizedSearch = searchValue.trim().toLowerCase();

    if (!normalizedSearch) {
      return users;
    }

    return users.filter((user) => {
      return (
        user.fullName.toLowerCase().includes(normalizedSearch) ||
        user.login.toLowerCase().includes(normalizedSearch) ||
        user.organization.toLowerCase().includes(normalizedSearch)
      );
    });
  }, [searchValue, users]);

  const handleSearchSubmit = () => {
    console.log('Поиск пользователя:', searchValue);
  };

  const handleCreateUser = async (values: UserFormValues) => {
    try {
      const newUser = await createAdminUser(values);
      setUsers((prevUsers) => [...prevUsers, newUser]);
      setIsCreateOpen(false);
    } catch (error) {
      console.error(error);
    }
  };

  const handleEditUser = async (values: UserFormValues) => {
    if (!editUser) {
      return;
    }

    try {
      const updatedUser = await updateAdminUser(editUser.id, values);

      setUsers((prevUsers) =>
        prevUsers.map((user) => (user.id === editUser.id ? updatedUser : user))
      );

      setEditUser(null);
    } catch (error) {
      console.error(error);
    }
  };

  const handleDeleteUser = (userToDelete: User) => {
    setUsers((prevUsers) =>
      prevUsers.filter((user) => user.id !== userToDelete.id)
    );
  };
  return (
    <div className={cls.page}>
      <AdminUsersToolbar
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        onSearchSubmit={handleSearchSubmit}
      />

      <section className={cls.section}>
        <div className={cls.sectionHeader}>
          <h1 className={cls.title}>Все пользователи</h1>

          <button
            type="button"
            className={cls.createButton}
            onClick={() => setIsCreateOpen(true)}
            aria-label="Создать пользователя"
          >
            <img
              src={addIcon}
              alt=""
              className={cls.addIcon}
            />
          </button>
        </div>

        {loadError && <p>{loadError}</p>}

        <UsersTable
          users={filteredUsers}
          onViewUser={setViewUser}
          onEditUser={setEditUser}
          onDeleteUser={handleDeleteUser}
        />
      </section>

      <UserFormModal
        isOpen={isCreateOpen}
        title="Создание пользователя"
        submitText="Создать"
        passwordLabel="Пароль"
        isPasswordRequired
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreateUser}
      />

      <UserFormModal
        isOpen={Boolean(editUser)}
        title="Редактирование пользователя"
        submitText="Сохранить"
        initialUser={editUser}
        passwordLabel="Новый пароль"
        isPasswordRequired={false}
        onClose={() => setEditUser(null)}
        onSubmit={handleEditUser}
      />

      <UserInfoModal
        isOpen={Boolean(viewUser)}
        user={viewUser}
        onClose={() => setViewUser(null)}
      />
    </div>
  );
};
