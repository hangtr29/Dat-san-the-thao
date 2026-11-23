/**
 * App - Định tuyến chính của SPA React.
 */
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import Header from '@/components/Header'
import Footer from '@/components/Footer'
import { LoadingScreen, ToastContainer } from '@/components/ui'

// --- Pages ---
import Home from '@/pages/Home'
import FacilityList from '@/pages/FacilityList'
import FacilityDetail from '@/pages/FacilityDetail'
import { LoginPage, RegisterPage } from '@/pages/Auth'
import {
  BookingTermsPage,
  RefundPolicyPage,
  BookingLookupPage,
} from '@/pages/Legal'

// Lazy load các trang không thường xuyên dùng
const MyBookings = lazy(() => import('@/pages/MyBookings'))
const Notifications = lazy(() => import('@/pages/Notifications'))
const OwnerDashboard = lazy(() => import('@/pages/OwnerDashboard'))
const MapPage = lazy(() => import('@/pages/MapPage'))
const Favorites = lazy(() => import('@/pages/Favorites'))
const Profile = lazy(() => import('@/pages/Profile'))
const NotFound = lazy(() => import('@/pages/NotFound'))

/**
 * ProtectedRoute - Chặn trang yêu cầu đăng nhập.
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) return <LoadingScreen label="Đang kiểm tra phiên đăng nhập..." />

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  return children
}

/**
 * OwnerRoute - Chặn trang dành riêng cho chủ sân.
 */
function OwnerRoute({ children }) {
  const { isOwner, isAdmin, loading } = useAuth()

  if (loading) return <LoadingScreen label="Đang kiểm tra quyền..." />

  if (!isOwner && !isAdmin) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <div className="mb-4 text-5xl">🚫</div>
        <h1 className="text-xl font-bold text-slate-900">
          Bạn không có quyền truy cập
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Trang này chỉ dành cho chủ sân và quản trị viên.
        </p>
      </div>
    )
  }

  return children
}

function AppRoutes() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="flex-1 pb-20 md:pb-0">
        <Suspense fallback={<LoadingScreen />}>
          <Routes>
            {/* Public */}
            <Route path="/" element={<Home />} />
            <Route path="/facilities" element={<FacilityList />} />
            <Route path="/facilities/:id" element={<FacilityDetail />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/terms" element={<BookingTermsPage />} />
            <Route path="/refund-policy" element={<RefundPolicyPage />} />
            <Route path="/lookup" element={<BookingLookupPage />} />

            {/* Protected */}
            <Route
              path="/bookings"
              element={
                <ProtectedRoute>
                  <MyBookings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/notifications"
              element={
                <ProtectedRoute>
                  <Notifications />
                </ProtectedRoute>
              }
            />
            <Route
              path="/favorites"
              element={
                <ProtectedRoute>
                  <Favorites />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <Profile />
                </ProtectedRoute>
              }
            />

            {/* Owner */}
            <Route
              path="/owner"
              element={
                <ProtectedRoute>
                  <OwnerRoute>
                    <OwnerDashboard />
                  </OwnerRoute>
                </ProtectedRoute>
              }
            />

            {/* 404 */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>

      {/* Footer */}
      <Footer />

      <ToastContainer />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
