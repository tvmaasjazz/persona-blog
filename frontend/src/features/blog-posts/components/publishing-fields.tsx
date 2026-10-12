import { withFieldGroup } from '@/components/form/use-app-form'
import {
  EMPTY_PUBLISHING_VALUES,
  type PublishingFormValues,
} from '@/features/blog-posts/publishing-form-schema'

type PublishingFieldsProps = {
  isPersonaPublic: boolean
}

// The publishing controls, reusable inside any form that nests PublishingFormValues:
// <PublishingFields form={form} fields="publishing" isPersonaPublic={...} />
export const PublishingFields = withFieldGroup({
  defaultValues: EMPTY_PUBLISHING_VALUES as PublishingFormValues,
  props: { isPersonaPublic: false } as PublishingFieldsProps,
  render: function PublishingFieldsRender({ group, isPersonaPublic }) {
    return (
      <div className="flex flex-col gap-5">
        <group.AppField name="isPublic">
          {(field) => (
            <field.SwitchField
              label="Public"
              description={
                isPersonaPublic
                  ? 'Other signed-in people can read a public post once it is published.'
                  : 'This persona is private, so its posts stay private. Make the persona public to share them.'
              }
              isDisabled={!isPersonaPublic}
            />
          )}
        </group.AppField>
        <group.AppField name="publishMode">
          {(field) => (
            <field.RadioGroupField
              label="Publishing"
              options={[
                { value: 'draft', label: 'Draft', description: 'Keep it to yourself for now.' },
                { value: 'now', label: 'Publish now' },
                { value: 'schedule', label: 'Schedule', description: 'Publish at a set time.' },
              ]}
            />
          )}
        </group.AppField>
        <group.Subscribe selector={(state) => state.values.publishMode}>
          {(publishMode) =>
            publishMode === 'schedule' && (
              <group.AppField name="scheduledAt">
                {(field) => <field.DateTimeField label="Publish at" />}
              </group.AppField>
            )
          }
        </group.Subscribe>
      </div>
    )
  },
})
