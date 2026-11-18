import type { ProfileOut, ResumeDraftOut } from '../types'

const profileContent =
  'Junior software developer focused on Python, FastAPI, and SQL. Built small web apps with React and PostgreSQL. Comfortable with Git, basic Docker, and writing clear documentation. Looking for remote entry-level backend work where I can keep learning.\n\nContact: jordan.lee@example.com'

export const profileSample: ProfileOut = {
  content: profileContent,
  updated_at: '2026-02-12T09:30:00+08:00',
  char_count: profileContent.length,
  groq_view:
    'Junior software developer focused on Python, FastAPI, and SQL. Built small web apps with React and PostgreSQL. Comfortable with Git, basic Docker, and writing clear documentation. Looking for remote entry-level backend work where I can keep learning.\n\nContact: [removed]',
  redactions: {
    emails: 1,
    phones: 0,
    lines: 1,
  },
  warnings: ['Sample data only. No real profile was loaded.'],
}

export const resumeDraftSample: ResumeDraftOut = {
  skills: ['Python', 'FastAPI', 'SQL', 'React', 'Git', 'Docker'],
  draft_content:
    'Python developer with hands-on experience building small FastAPI services and React interfaces. Comfortable working with SQL databases, Git workflows, and clear technical documentation. Seeking remote entry-level backend work with room to grow.',
  pages: 2,
  extracted_chars: 3800,
  truncated: false,
  redactions: {
    emails: 1,
    phones: 1,
    lines: 2,
    urls: 1,
    address_lines: 1,
  },
  dropped_skills: 0,
  warnings: [],
}
