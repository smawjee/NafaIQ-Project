
--create table
CREATE TABLE public.goals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  name TEXT NOT NULL,

  target NUMERIC NOT NULL,

  saved NUMERIC NOT NULL DEFAULT 0,

  emoji TEXT,

  color TEXT,

  ai TEXT,

  target_date DATE,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

--alert table

ALTER TABLE public.goals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own goals"
ON public.goals
FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own goals"
ON public.goals
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own goals"
ON public.goals
FOR UPDATE
TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own goals"
ON public.goals
FOR DELETE
TO authenticated
USING (auth.uid() = user_id);



--function

CREATE OR REPLACE FUNCTION public.update_goals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER update_goals_updated_at
BEFORE UPDATE ON public.goals
FOR EACH ROW
EXECUTE FUNCTION public.update_goals_updated_at();

