import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Shell from './components/Shell'
import Dashboard from './pages/Dashboard'
import JobHunter from './pages/JobHunter'
import JobsToApply from './pages/JobsToApply'
import Applications from './pages/Applications'
import Notifications from './pages/Notifications'
import FollowUps from './pages/FollowUps'
import ApplicationEmails from './pages/ApplicationEmails'
import MyProfile from './pages/MyProfile'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/job-hunter" element={<JobHunter />} />
          <Route path="/jobs" element={<JobsToApply />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/follow-ups" element={<FollowUps />} />
          <Route path="/emails" element={<ApplicationEmails />} />
          <Route path="/profile" element={<MyProfile />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}