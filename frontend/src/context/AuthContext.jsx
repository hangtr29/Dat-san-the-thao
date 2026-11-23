/**
 * AuthContext - Quản lý trạng thái xác thực toàn cục.
 *
 * Tích hợp với JWT của Django REST Framework:
 * - Đăng nhập -> lưu access/refresh token vào localStorage
 * - Tự động xóa token khi hết hạn (sự kiện 'auth:expired')
 */
import { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react'
import { authApi, tokenStorage } from '@/lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => tokenStorage.getUser())
  const [loading, setLoading] = useState(true)

  // Kiểm tra token còn hợp lệ khi khởi động app
  useEffect(() => {
    let cancelled = false

    const verify = async () => {
      const token = tokenStorage.getAccess()
      if (!token) {
        setLoading(false)
        return
      }
      try {
        const me = await authApi.me()
        if (!cancelled) setUser(me)
      } catch {
        if (!cancelled) {
          tokenStorage.clear()
          setUser(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    verify()
    return () => {
      cancelled = true
    }
  }, [])

  // Lắng nghe sự kiện hết hạn token từ interceptor
  useEffect(() => {
    const handleExpired = () => {
      setUser(null)
      tokenStorage.clear()
    }
    window.addEventListener('auth:expired', handleExpired)
    return () => window.removeEventListener('auth:expired', handleExpired)
  }, [])

  const login = useCallback(async (credentials) => {
    const data = await authApi.login(credentials)
    setUser(data.user)
    return data
  }, [])

  const register = useCallback(async (payload) => {
    const data = await authApi.register(payload)
    setUser(data.user)
    return data
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: !!user,
      isOwner: user?.role === 'OWNER',
      isAdmin: user?.role === 'ADMIN' || user?.is_staff,
      login,
      register,
      logout,
    }),
    [user, loading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth phải được dùng bên trong <AuthProvider>')
  }
  return ctx
}
