export type QuestionType = 'text' | 'mc';

export interface Question {
  id: string;
  num: string;
  text: string;
  type: QuestionType;
  options?: string[] | null;
  multi_select: boolean;
  comment_prompt?: string | null;
  references?: string[] | null;
}

export interface Answer {
  question_id: string;
  value?: string | null;     // null means skipped
  choices?: string[] | null;
  comment?: string | null;
  updated_at?: string | null;
}

export interface CandidateView {
  name: string;
  status: 'not_started' | 'in_progress' | 'submitted';
  submitted_at: string | null;
  read_only: boolean;
  questions: Question[];
  answers: Record<string, Answer>;
  answered: number;
  total: number;
}

export interface SubmitPreview {
  total: number;
  answered: number;
  unanswered: string[];
  already_submitted: boolean;
}

export interface CandidateRow {
  id: number;
  name: string;
  email: string | null;
  status: string;
  answered: number;
  total: number;
  created_at: string;
  submitted_at: string | null;
  link: string;
}

export interface ComparisonPart {
  verdict: string;
  summary: string | null;
  detail: any;
  model: string | null;
  deterministic: boolean;
  created_at: string;
}

export interface AdminQuestionRow extends Question {
  baseline: string | null;
  baseline_choices: string[] | null;
  baseline_note: string | null;
  comment_baseline: string | null;
  answer: { value: string | null; choices: string[] | null; comment: string | null } | null;
  comparison: Record<string, ComparisonPart>;
}

export interface CandidateDetail {
  id: number;
  name: string;
  email: string | null;
  status: string;
  submitted_at: string | null;
  questions: AdminQuestionRow[];
  notes: { id: number; body: string; updated_at: string }[];
}
