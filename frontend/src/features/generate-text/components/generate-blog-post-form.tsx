import { FormSection } from '@/components/form/form-section'
import { withForm } from '@/components/form/use-app-form'
import { Button } from '@/components/ui/button'
import { generateBlogPostFormOptions } from '@/features/generate-text/generate-blog-post-form-schema'

export type PersonaChoice = {
  identity: string
  name: string
  default_tone: string | null
  default_target_audience: string | null
}

// The generate form's fields and button. GenerateBlogPostForm owns what submitting does.
export const GenerateBlogPostForm = withForm({
  ...generateBlogPostFormOptions,
  props: {
    personas: [] as PersonaChoice[],
  },
  render: function GenerateBlogPostFormRender({ form, personas }) {
    return (
      <form
        noValidate
        className="flex flex-col gap-8"
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        <FormSection title="Brief">
          <form.AppField
            name="persona_identity"
            listeners={{
              onChange: ({ value }) => {
                const persona = personas.find((choice) => choice.identity === value)
                if (!persona) {
                  return
                }
                form.setFieldValue('tone', persona.default_tone ?? '')
                form.setFieldValue('target_audience', persona.default_target_audience ?? '')
              },
            }}
          >
            {(field) => (
              <field.SelectField
                label="Persona"
                placeholder="Choose a persona"
                options={personas.map((persona) => ({
                  value: persona.identity,
                  label: persona.name,
                }))}
              />
            )}
          </form.AppField>
          <form.AppField name="prompt_text">
            {(field) => (
              <field.TextareaField
                label="Prompt"
                description="What the post is about. For example: Five weeknight dinners that take twenty minutes."
              />
            )}
          </form.AppField>
          <form.AppField name="tone">{(field) => <field.TextField label="Tone" />}</form.AppField>
          <form.AppField name="target_audience">
            {(field) => <field.TextField label="Target audience" />}
          </form.AppField>
          <form.AppField name="additional_context">
            {(field) => (
              <field.TextareaField
                label="Additional context"
                description="Optional. Facts, links, or notes the post should draw on."
              />
            )}
          </form.AppField>
        </FormSection>

        <FormSection title="Steps">
          <div className="flex flex-col gap-4">
            <h3 className="text-sm font-semibold">Outline</h3>
            <form.AppField name="isOutlineEnabled">
              {(field) => <field.SwitchField label="Write an outline first" />}
            </form.AppField>
            <form.AppField name="isOutlineAutoApproved">
              {(field) => <field.SwitchField label="Approve the outline automatically" />}
            </form.AppField>
          </div>
          <div className="flex flex-col gap-4">
            <h3 className="text-sm font-semibold">Draft</h3>
            <form.AppField name="isDraftAutoApproved">
              {(field) => (
                <field.SwitchField
                  label="Approve the draft automatically"
                  description="The draft is always written."
                />
              )}
            </form.AppField>
          </div>
          <div className="flex flex-col gap-4">
            <h3 className="text-sm font-semibold">Humanize</h3>
            <form.AppField name="isHumanizeEnabled">
              {(field) => <field.SwitchField label="Humanize the draft" />}
            </form.AppField>
            <form.AppField name="isHumanizeAutoApproved">
              {(field) => <field.SwitchField label="Approve the humanized draft automatically" />}
            </form.AppField>
          </div>
        </FormSection>

        <form.Subscribe selector={(formState) => formState.isSubmitting}>
          {(isSubmitting) => (
            <div className="flex flex-col items-start gap-2">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Writing…' : 'Write post'}
              </Button>
              {isSubmitting && (
                <p className="text-sm text-muted-foreground">
                  This can take a minute or more. Keep this page open.
                </p>
              )}
            </div>
          )}
        </form.Subscribe>
      </form>
    )
  },
})
