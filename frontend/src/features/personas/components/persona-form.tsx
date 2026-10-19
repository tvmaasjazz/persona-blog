import { FormSection } from '@/components/form/form-section'
import { withForm } from '@/components/form/use-app-form'
import { Button } from '@/components/ui/button'
import { personaFormOptions } from '@/features/personas/persona-form-schema'

// The persona form's fields; the parent owns submitting.
export const PersonaForm = withForm({
  ...personaFormOptions,
  props: {
    submitLabel: '',
    onCancel: () => {},
  },
  render: function PersonaFormRender({ form, submitLabel, onCancel }) {
    return (
      <form
        noValidate
        className="flex flex-col gap-8"
        onSubmit={(event) => {
          event.preventDefault()
          void form.handleSubmit()
        }}
      >
        {/* Profile */}
        <FormSection title="Profile">
          <form.AppField name="name">
            {(field) => (
              <field.TextField
                label="Name"
                description="The pen name readers see. For example: Maya Okafor."
              />
            )}
          </form.AppField>
          <form.AppField name="bio">
            {(field) => (
              <field.TextareaField
                label="Bio"
                description="A sentence or two for the top of their profile. For example: Former line cook writing about fast weeknight dinners for people with no time."
                rows={3}
              />
            )}
          </form.AppField>
          <form.AppField name="avatar_url">
            {(field) => (
              <field.TextField
                label="Avatar URL"
                description="A link to a square image. Uploads are coming. For example: https://example.com/maya.png"
                type="url"
              />
            )}
          </form.AppField>
          <form.AppField name="is_public">
            {(field) => (
              <field.SwitchField
                label="Public"
                description="Other signed-in people can view a public persona's profile. Only you can edit it."
              />
            )}
          </form.AppField>
        </FormSection>

        {/* Voice */}
        <FormSection title="Voice">
          <form.AppField name="background">
            {(field) => (
              <field.TextareaField
                label="Background"
                description="The backstory that shapes their point of view. For example: Grew up in Lagos, cooked in restaurants for ten years, now raising two kids in Chicago."
              />
            )}
          </form.AppField>
          <form.AppField name="writing_style">
            {(field) => (
              <field.TextareaField
                label="Writing style"
                description="How their sentences read: length, vocabulary, formatting habits. For example: Short paragraphs, plain words, a numbered list for any steps, one joke per post."
              />
            )}
          </form.AppField>
          <form.AppField name="sample_writing">
            {(field) => (
              <field.TextareaField
                label="Sample writing"
                description="A passage in their voice for the model to imitate. A few paragraphs is plenty."
                rows={10}
              />
            )}
          </form.AppField>
        </FormSection>

        {/* Defaults */}
        <FormSection title="Defaults">
          <form.AppField name="default_tone">
            {(field) => (
              <field.TextField
                label="Default tone"
                description="The tone a new post starts with. For example: Warm and a little wry."
              />
            )}
          </form.AppField>
          <form.AppField name="default_target_audience">
            {(field) => (
              <field.TextField
                label="Default target audience"
                description="Who they usually write for. For example: Busy parents who cook four nights a week."
              />
            )}
          </form.AppField>
        </FormSection>

        {/* Buttons */}
        <div className="flex gap-3">
          <form.AppForm>
            <form.SubmitButton label={submitLabel} />
          </form.AppForm>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    )
  },
})
